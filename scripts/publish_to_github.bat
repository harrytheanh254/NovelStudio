@echo off
setlocal EnableExtensions
chcp 65001 >nul
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "WORKTREE=%ROOT%\_github_publish_harrytheanh254"
set "REPO=https://github.com/harrytheanh254/NovelStudio.git"

echo =============================================
echo   SANH TRUYEN - Publish source to GitHub
echo =============================================
where git >nul 2>nul
if errorlevel 1 (
  echo Khong tim thay Git. Hay cai Git for Windows truoc.
  pause
  exit /b 1
)
if not exist "%ROOT%\app-desktop\main.py" (
  echo Khong tim thay %ROOT%\app-desktop\main.py
  echo Hay giai nen ZIP vao D:\NovelStudio truoc.
  pause
  exit /b 1
)
if not exist "%WORKTREE%\.git" (
  if exist "%WORKTREE%" (
    echo Thu muc %WORKTREE% da ton tai nhung khong phai Git checkout.
    echo Hay doi ten thu muc nay roi chay lai.
    pause
    exit /b 1
  )
  git clone "%REPO%" "%WORKTREE%"
  if errorlevel 1 (
    echo Clone that bai. Kiem tra Internet va quyen truy cap repository.
    pause
    exit /b 1
  )
)
if not exist "%WORKTREE%\.git" (
  echo Khong tim thay Git checkout trong %WORKTREE%.
  pause
  exit /b 1
)

for %%D in (app-desktop scripts tests) do if not exist "%WORKTREE%\%%D" mkdir "%WORKTREE%\%%D"
copy /Y "%ROOT%\README.md" "%WORKTREE%\README.md" >nul
copy /Y "%ROOT%\.gitignore" "%WORKTREE%\.gitignore" >nul
copy /Y "%ROOT%\REPO_UPLOAD_GUIDE.md" "%WORKTREE%\REPO_UPLOAD_GUIDE.md" >nul
copy /Y "%ROOT%\THIRD_PARTY_NOTICES.md" "%WORKTREE%\THIRD_PARTY_NOTICES.md" >nul
copy /Y "%ROOT%\requirements-translation.txt" "%WORKTREE%\requirements-translation.txt" >nul
xcopy "%ROOT%\app-desktop\*" "%WORKTREE%\app-desktop\" /E /I /Y >nul
xcopy "%ROOT%\scripts\*" "%WORKTREE%\scripts\" /E /I /Y >nul
if exist "%ROOT%\tests\*" xcopy "%ROOT%\tests\*" "%WORKTREE%\tests\" /E /I /Y >nul

pushd "%WORKTREE%"
git add README.md .gitignore REPO_UPLOAD_GUIDE.md THIRD_PARTY_NOTICES.md requirements-translation.txt app-desktop scripts tests
if errorlevel 1 goto git_error
git diff --cached --quiet
if not errorlevel 1 (
  echo Khong co thay doi moi can commit.
  goto done
)
git config user.name >nul 2>nul
if errorlevel 1 git config user.name "harrytheanh254"
git config user.email >nul 2>nul
if errorlevel 1 git config user.email "298678616+harrytheanh254@users.noreply.github.com"
git commit -m "Add NovelStudio desktop prototype v0.3"
if errorlevel 1 goto git_error
git push -u origin main
if errorlevel 1 (
  echo Push chua thanh cong. Kiem tra quyen ghi va dang nhap GitHub.
  popd
  pause
  exit /b 1
)
echo.
echo Thanh cong! Mo: https://github.com/harrytheanh254/NovelStudio
echo Code -^> Download ZIP de tai source.
goto done

:git_error
echo Git bao loi. Hay doc thong bao o tren; khong can gui mat khau/token cho ai.
popd
pause
exit /b 1

:done
popd
echo.
pause
endlocal
