# K7 网络自动切换守护服务

## 目标

K7 网关上电后应当自动选择可用网络，不需要每次人工执行 `nmcli`：

1. 优先使用 RG200U 5G/4G 模块。
2. 如果蜂窝网络暂时不可用，再尝试连接已保存的 WiFi。
3. WiFi 连上后也不能停止检查蜂窝网络；下一轮仍然要回头检查 5G/4G 是否恢复。
4. 如果 WiFi 热点没有打开，程序不能卡死，应继续循环检测蜂窝模块。

## 实现方式

新增命令：

```bash
PYTHONPATH=/root/k7-gateway/src python3 -m k7_gateway network-watchdog
```

该命令通过 NetworkManager 的 `nmcli` 管理网络连接：

- RG200U 常见网卡名：`enx*`、`usb*`、`wwan*`
- WiFi 常见网卡名：`wlan*`、`wlp*`
- 蜂窝连接 route metric：`100`
- WiFi 连接 route metric：`600`

Linux 会优先使用 metric 更小的默认路由，所以蜂窝网络恢复后会重新成为优先出口。

## 手动验证

只执行一轮检查：

```bash
PYTHONPATH=/root/k7-gateway/src python3 -m k7_gateway network-watchdog --once
```

查看当前默认出口：

```bash
ip route
```

查看 NetworkManager 设备状态：

```bash
nmcli device status
```

查看已保存连接：

```bash
nmcli connection show
```

## systemd 自启动

安装服务：

```bash
cd /root/k7-gateway
sh scripts/install_systemd_service.sh
```

该脚本会安装并启动两个服务：

- `k7-network-watchdog.service`：负责蜂窝优先、WiFi 兜底的网络守护。
- `k7-gateway.service`：负责 LoRa 收数、MQTT 上报、后台下发转 LoRa。

查看网络守护日志：

```bash
systemctl status k7-network-watchdog.service
journalctl -u k7-network-watchdog.service -n 80 --no-pager
```

查看网关业务日志：

```bash
systemctl status k7-gateway.service
journalctl -u k7-gateway.service -n 80 --no-pager
```

## 当前硬件注意事项

RG200U 现在如果没有螺丝固定，Mini-PCIe 接触可能会抖动。典型现象是：

- `/dev/ttyUSB0` 到 `/dev/ttyUSB4` 一会儿存在、一会儿消失。
- `nmcli device status` 里的 `enx*` 网卡名称反复变化。
- `dmesg` 出现 USB disconnect / reconnect。

软件守护服务只能在模块重新出现后继续连接，不能解决物理接触不良。稳定测试必须用合适螺丝固定模块。
