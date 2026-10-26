# BBDown binaries (not shipped)

This open-source export **does not** include BBDown executables (`BBDown`, `BBDown.exe`, `BBDown_Mac`).

## Why
Upstream BBDown binaries are large third-party builds. Shipping them bloats the repo and can trip antivirus / license confusion.

## How to get them
1. Download a release from the [BBDown project](https://github.com/nilaoda/BBDown) (or your preferred mirror).
2. Place the matching binary under `BBDown/` as:
   - Windows: `BBDown.exe` (or `BBDown`)
   - macOS: `BBDown_Mac` or `BBDown`
   - Linux: `BBDown`
3. Ensure the path matches `config` / docs for your platform.
4. Keep binaries **out of git** (already listed in `.gitignore`).

See also `BBDown_README.md` for CLI flags.
