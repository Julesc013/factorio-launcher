# generated source-sha256: 189d32dd9028370834a8a0ee2c450526841e6e20afe4023f28beaec65f96abb7
Register-ArgumentCompleter -Native -CommandName facman -ScriptBlock { param($wordToComplete) 'diagnostics doctor export import installs instances launch mods modsets product run saves setup workspace'.Split(' ') | Where-Object { $_ -like "$wordToComplete*" } }
