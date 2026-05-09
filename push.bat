git add .

git diff --cached --quiet
if %errorlevel%==0 (
    echo Nothing to commit
) else (
    git commit -m "auto update"
    git push
)

pause