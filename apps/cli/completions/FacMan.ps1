# generated source-sha256: c578bafc3e92d783e8ffa22986c46fcf5db689e91f3889c797c06dda03651cd6
Register-ArgumentCompleter -Native -CommandName facman -ScriptBlock { param($wordToComplete) 'diagnostics doctor export import installs instances launch mods modsets product run saves workspace'.Split(' ') | Where-Object { $_ -like "$wordToComplete*" } }
