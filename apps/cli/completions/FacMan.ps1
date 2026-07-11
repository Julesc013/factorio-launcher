# generated source-sha256: 6ecfc8b073bdfb30f272c366abe84ddd8e0a779fb124e35666d58ebd5345f42c
Register-ArgumentCompleter -Native -CommandName facman -ScriptBlock { param($wordToComplete) 'diagnostics doctor export import installs instances launch mods modsets product run saves workspace'.Split(' ') | Where-Object { $_ -like "$wordToComplete*" } }
