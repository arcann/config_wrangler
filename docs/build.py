from sphinx.cmd.build import main as sphinx_main

# Arguments look exactly like the terminal input arrays
args = ["-b", "html", "-E", "-N", "source", "build"]

# Returns 0 on success, or an error exit code
exit_code = sphinx_main(args)

if exit_code == 0:
    print("Build finished perfectly!")
else:
    print(f"Sphinx failed with code: {exit_code}")