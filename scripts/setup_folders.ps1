$root = 'D:\NovelStudio'
$folders = @(
  "$root\vendor",
  "$root\app-desktop",
  "$root\data\epub",
  "$root\data\raw",
  "$root\data\translated",
  "$root\data\audio",
  "$root\cache\pip",
  "$root\temp",
  "$root\envs"
)
foreach ($folder in $folders) {
  New-Item -ItemType Directory -Force -Path $folder | Out-Null
}
Write-Host "Da kiem tra/tao cac thu muc trong $root"
