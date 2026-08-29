param(
    [string]$Name = "GiveawaysTools"
)

$ErrorActionPreference = "Stop"

uv run --with pyinstaller pyinstaller `
    --noconsole `
    --onefile `
    --clean `
    --name $Name `
    --paths src `
    --collect-all PyQt6 `
    --add-data "assets;assets" `
    main_ui.py
