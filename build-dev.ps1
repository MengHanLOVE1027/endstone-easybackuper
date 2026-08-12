cd ~\Desktop\Plugins-Dev\EndStone\Projects\endstone-easybackuper\

Write-Host "=== 清理旧产物 ===" -ForegroundColor Cyan
Remove-Item '.\dist\*' -Recurse -ErrorAction SilentlyContinue

Write-Host "=== 构建 wheel ===" -ForegroundColor Cyan
python -m build --wheel

Write-Host "=== 部署到服务器 ===" -ForegroundColor Cyan
Remove-Item 'C:\Users\HeYuHan\Desktop\Plugins-Dev\EndStone\bedrock_server\plugins\endstone_easybackuper*.whl' -ErrorAction SilentlyContinue
Copy-Item -Path 'C:\Users\HeYuHan\Desktop\Plugins-Dev\EndStone\Projects\endstone-easybackuper\dist\end*.whl' -Destination 'C:\Users\HeYuHan\Desktop\Plugins-Dev\EndStone\bedrock_server\plugins'

Write-Host "=== 完成，启动服务器 ===" -ForegroundColor Green
Get-ChildItem 'C:\Users\HeYuHan\Desktop\Plugins-Dev\EndStone\bedrock_server\plugins\endstone_easybackuper*.whl'
cd ~\Desktop\Plugins-Dev\EndStone\
start .\start.cmd