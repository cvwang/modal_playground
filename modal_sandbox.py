import modal

stub = modal.Stub("example-get-started")

@stub.local_entrypoint()
def main():
    sb = stub.app.spawn_sandbox(
        "bash",
        "-c",
        "cd /repo && pytest .",
        image=modal.Image.debian_slim().pip_install("pandas"),
        mounts=[modal.Mount.from_local_dir("./my_repo", remote_path="/repo")],
        timeout=600, # 10 minutes
    )

    sb.wait()

    if sb.returncode != 0:
        print(f"Tests failed with code {sb.returncode}")
        print(sb.stderr.read())