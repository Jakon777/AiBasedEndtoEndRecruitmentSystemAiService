import subprocess, tempfile, os, shutil

DOCKER_IMAGE="python:3.10-slim"
TIME_LIMIT=50

def evaluate_code(code, test_cases):
    temp_dir=tempfile.mkdtemp()
    file_path=os.path.join(temp_dir,"solution.py")

    try:
        with open(file_path,"w") as f:
            f.write(code)

        results=[]
        for case in test_cases:
            process=subprocess.run(
                ["docker","run","--rm",
                 "-v",f"{temp_dir}:/app",
                 "-w","/app",
                 DOCKER_IMAGE,
                 "python","solution.py"],
                input=case["input"].encode(),
                stdout=subprocess.PIPE,
                timeout=TIME_LIMIT
            )

            output=process.stdout.decode().strip()
            results.append({
                "input":case["input"],
                "expected":case["expected_output"],
                "output":output,
                "passed":output==case["expected_output"].strip()
            })

        passed=sum(r["passed"] for r in results)
        total=len(results)

        return {
            "score":(passed/total)*100 if total else 0,
            "details":results
        }

    finally:
        shutil.rmtree(temp_dir)
