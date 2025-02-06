@echo off
SET TERRAFORM_VERSION=1.6.0
SET INSTALL_PATH=C:\Users\Diego\Documents\Robo Trader\robo_arbitragem_telegram_cloud\

echo Criando pasta para o Terraform...
mkdir %INSTALL_PATH%

echo Baixando Terraform...
powershell -Command "Invoke-WebRequest -Uri 'https://releases.hashicorp.com/terraform/%TERRAFORM_VERSION%/terraform_%TERRAFORM_VERSION%_windows_amd64.zip' -OutFile '%TEMP%\terraform.zip'"

echo Extraindo Terraform...
powershell -Command "Expand-Archive -Path '%TEMP%\terraform.zip' -DestinationPath '%INSTALL_PATH%' -Force"

echo Adicionando ao PATH...
setx PATH "%INSTALL_PATH%;%PATH%"

echo Terraform instalado com sucesso!
terraform --version

pause
