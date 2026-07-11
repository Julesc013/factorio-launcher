# generated source-sha256: 3af1fd22c531d40be456cf439739507c06d0b4310b2fe7574d0df45e904bef7e
Register-ArgumentCompleter -Native -CommandName facman -ScriptBlock { param($wordToComplete) 'diagnostics doctor export import installs instances launch mods modsets product run saves setup workspace'.Split(' ') | Where-Object { $_ -like "$wordToComplete*" } }
