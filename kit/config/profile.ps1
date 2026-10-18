# node via fnm, once per shell (the 5.1 profile may have beaten us to it)
if ((Get-Command fnm -ErrorAction SilentlyContinue) -and -not $env:FNM_MULTISHELL_PATH) {
  fnm env --use-on-cd --shell powershell | Out-String | Invoke-Expression
}

# interactive shells only; scripts and agents get stock powershell
$edithArgs = [Environment]::GetCommandLineArgs()
$edithInteractive = [Environment]::UserInteractive -and -not ($edithArgs -match '^-noni') -and
  (($edithArgs -match '^-noe') -or -not ($edithArgs -match '^-(c|com|command|f|file|e|ec|encodedcommand)$'))

if ($edithInteractive) {
  if (Get-Command starship -ErrorAction SilentlyContinue) { Invoke-Expression (& starship init powershell) }
  if (Get-Command zoxide -ErrorAction SilentlyContinue) { Invoke-Expression (& { (zoxide init powershell | Out-String) }) }

  if (Get-Command eza -ErrorAction SilentlyContinue) {
    Remove-Item Alias:ls -Force -ErrorAction SilentlyContinue
    function ls { eza --group-directories-first --icons=auto @args }
    function ll { eza -la --group-directories-first --git --icons=auto @args }
    function lt { eza --tree --level=2 --group-directories-first --icons=auto @args }
  }
  if (Get-Command bat -ErrorAction SilentlyContinue) { function b { bat --style=plain @args } }
  if (Get-Command lazygit -ErrorAction SilentlyContinue) { Set-Alias lg lazygit }

  # proj: pick any project under the profile's roots and jump there
  if ((Get-Command edith -ErrorAction SilentlyContinue) -and (Get-Command fzf -ErrorAction SilentlyContinue)) {
    function proj {
      $pick = edith projects --paths | fzf --height 40% --reverse --prompt 'project > ' --query "$args"
      if ($pick) { Set-Location -LiteralPath $pick }
    }
  }

  try {
    Set-PSReadLineOption -ErrorAction Stop -Colors @{
      Command = '#3dd6f5'; Parameter = '#a78bfa'; String = '#4be3a0'; Number = '#f7c548'
      Operator = '#d5dee8'; Variable = '#d5dee8'; Comment = '#6a758a'
    }
  } catch { }
  # psreadline 2.1+ only; windows powershell ships 2.0
  try { Set-PSReadLineOption -ErrorAction Stop -Colors @{ InlinePrediction = '#6a758a' } } catch { }
}
Remove-Variable edithArgs, edithInteractive
