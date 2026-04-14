#!/usr/bin/env bash
set -e

#
# 启动流光 Glance 网页版开发环境。
#

if ! command -v pnpm >/dev/null 2>&1; then
  echo "未检测到 pnpm，请先安装 pnpm。"
  exit 1
fi

pnpm install
pnpm start
