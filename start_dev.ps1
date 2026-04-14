$ErrorActionPreference = "Stop"

function Start-GlanceWeb {
    <#
    .SYNOPSIS
    启动流光 Glance 网页版开发环境。
    #>
    if (!(Get-Command pnpm -ErrorAction SilentlyContinue)) {
        throw "未检测到 pnpm，请先安装 pnpm。"
    }

    pnpm install
    pnpm start
}

Start-GlanceWeb
