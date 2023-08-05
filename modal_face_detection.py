import os

import modal

OUTPUT_DIR = "/tmp/"
FACE_CASCADE_FN = "haarcascade_frontalface_default.xml"

image = (
    modal.Image.debian_slim()
    .apt_install("libgl1-mesa-glx", "libglib2.0-0", "wget", "git")
    .run_commands(
        f"wget https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/{FACE_CASCADE_FN} -P /root"
    )
    .pip_install(
        "pytube @ git+https://github.com/felipeucelli/pytube",
        "opencv-python~=4.7.0.72",
        "moviepy~=1.0.3",
    )
)
stub = modal.Stub("example-youtube-face-detection", image=image)

if stub.is_inside():
    import cv2
    import moviepy.editor
    import pytube


stub.net_file_system = modal.NetworkFileSystem.new()


@stub.function(
    network_file_systems={"/clips": stub.net_file_system}, timeout=600
)
def detect_faces(fn, start, stop):
    # Extract the subclip from the video
    clip = moviepy.editor.VideoFileClip(fn).subclip(start, stop)

    # Load face detector
    face_cascade = cv2.CascadeClassifier(f"/root/{FACE_CASCADE_FN}")

    # Run face detector on frames
    imgs = []
    for img in clip.iter_frames():
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        for x, y, w, h in faces:
            cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 0), 2)
        imgs.append(img)

    # Create mp4 of result
    out_clip = moviepy.editor.ImageSequenceClip(imgs, fps=clip.fps)
    out_fn = f"/clips/{start:04d}.mp4"
    out_clip.write_videofile(out_fn)
    return out_fn


@stub.function(network_file_systems={"/clips": stub.net_file_system}, retries=1)
def process_video(url):
    print(f"Downloading video from '{url}'")
    yt = pytube.YouTube(url)
    stream = yt.streams.filter(file_extension="mp4").first()
    fn = stream.download(output_path="/clips/", max_retries=5)

    # Get duration
    duration = moviepy.editor.VideoFileClip(fn).duration

    # Create (start, stop) intervals
    intervals = [(fn, offset, offset + 1) for offset in range(int(duration))]

    print("Processing each range of 1s intervals using a Modal map")
    out_fns = list(detect_faces.starmap(intervals))

    print("Converting detections to video clips")
    out_clips = [moviepy.editor.VideoFileClip(out_fn) for out_fn in out_fns]

    print("Concatenating results")
    final_clip = moviepy.editor.concatenate_videoclips(out_clips)
    final_fn = "/clips/out.mp4"
    final_clip.write_videofile(final_fn)

    # Return the full image data
    with open(final_fn, "rb") as f:
        return os.path.basename(fn), f.read()


@stub.local_entrypoint()
# def main(youtube_url: str = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"):
def main(youtube_url: str = "https://www.youtube.com/watch?v=aPNB2h0TnXw"): # Fresh Prince
    fn, movie_data = process_video.call(youtube_url)
    abs_fn = os.path.join(OUTPUT_DIR, fn)
    print(f"writing results to {abs_fn}")
    with open(abs_fn, "wb") as f:
        f.write(movie_data)

