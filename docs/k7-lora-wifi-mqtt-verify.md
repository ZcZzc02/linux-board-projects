# K7 LoRa + WiFi + MQTT 验证记录

本文记录 KICKPI K7 在官方 Ubuntu 镜像基础上，通过 resource 版 boot 启用 UART3 后，复现老网关板“节点 LoRa 通信 + WiFi 上报后台”的验证方法。

## 当前结论

- K7 屏幕已正常显示。
- K7 已通过 WiFi 获取地址：`172.20.10.3`。
- K7 ADB 在线：`f776335ee852eb19 device`。
- LoRa 模块接在 UART3，对应 Linux 设备：`/dev/ttyS3`。
- 运行时设备树状态：
  - `/proc/device-tree/serial@2ad60000/status` 为 `okay`。
  - `/proc/device-tree/i2c@2aca0000/status` 为 `disabled`。
- 节点板开启后，K7 能持续收到真实 AD7606 LoRa 数据帧。
- K7 能通过 WiFi 将 LoRa 数据发布到 MQTT broker。
- 本机后台 `http://127.0.0.1:8001` 能接收 MQTT 数据并写入数据库。

## 已验证环境

- 开发板：KICKPI K7
- 芯片：RK3576
- 系统：KICKPI 官方 Ubuntu 24.04 镜像
- 内核：`Linux kickpi 6.1.75 #24 SMP Mon Nov 17 19:39:47 CST 2025 aarch64`
- 网络：WiFi 热点
- MQTT broker：`broker.emqx.io:1883`
- topic：`fengyan_daq_2026/data/node/1/ad7606`
- K7 网关程序路径：`/root/k7-gateway`
- 本机后台端口：`127.0.0.1:8001`

## K7 基础检查

Windows 侧使用项目内或工具目录里的 ADB：

```powershell
& 'D:\tools\platform-tools\adb.exe' devices
& 'D:\tools\platform-tools\adb.exe' shell "ip -br addr; uname -a"
```

成功现象：

```text
f776335ee852eb19    device
wlan0 UP 172.20.10.3/28 ...
Linux kickpi 6.1.75 ...
```

检查 UART3 / I2C7 运行时状态：

```powershell
& 'D:\tools\platform-tools\adb.exe' shell "cat /proc/device-tree/serial@2ad60000/status; echo; cat /proc/device-tree/i2c@2aca0000/status; echo; ls -l /dev/ttyS3 /dev/i2c-7 2>/dev/null"
```

成功现象：

- UART3 为 `okay`。
- I2C7 为 `disabled`。
- `/dev/ttyS3` 存在。
- `/dev/i2c-7` 不存在或不可用。

## LoRa 接收验证

节点板打开后，在 K7 上监听 UART3：

```powershell
& 'D:\tools\platform-tools\adb.exe' shell "cd /root/k7-gateway && PYTHONPATH=src timeout 30 python3 -m k7_gateway listen-lora --device /dev/ttyS3 --seconds 25 --raw"
```

成功现象：

```text
Listening /dev/ttyS3 at 9600 for 25.0s
RX_HEX=010110...
{"topic": "fengyan_daq_2026/data/node/1/ad7606", "payload": {...}}
```

实测能收到节点 `1` 的 AD7606 数据，通道电压约在 `1790 mV` 到 `1810 mV` 附近波动。

## 后台启动状态

本机后台使用 `8001` 端口连接 `broker.emqx.io`。检查监听端口：

```powershell
netstat -ano | Select-String ':8001'
```

检查后台日志：

```powershell
Get-Content -Path 'D:\rk3576开发\work\backend8001.err.log' -Tail 80
```

成功现象：

```text
已连接到 MQTT Broker: broker.emqx.io:1883
已订阅 topic: fengyan_daq_2026/data/node/+/ad7606
```

## K7 通过 WiFi 上报后台

在 K7 上运行 LoRa 网关程序，并把解析后的数据发布到 MQTT：

```powershell
& 'D:\tools\platform-tools\adb.exe' shell "cd /root/k7-gateway && PYTHONPATH=src timeout 35 python3 -m k7_gateway run-lora --device /dev/ttyS3 --seconds 25 --raw-log /tmp/lora.raw.log --log /tmp/lora.jsonl --mqtt-broker broker.emqx.io --transport wifi"
```

成功现象：

```text
Running LoRa gateway on /dev/ttyS3 at 9600
MQTT_BROKER=broker.emqx.io:1883
{"topic":"fengyan_daq_2026/data/node/1/ad7606","payload":{...}}
```

## 后台入库验证

查询原始帧：

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/frames?limit=3' | ConvertTo-Json -Depth 8
```

查询 AD7606 解析记录：

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/ad7606?limit=3' | ConvertTo-Json -Depth 8
```

成功现象：

```json
{
  "id": 30622,
  "node_addr": 1,
  "frame_type": 1,
  "type_name": "AD7606",
  "raw_hex": "0101102E122E052E012E012DFD2E032E0A2E0A6D70",
  "crc_ok": true,
  "topic": "fengyan_daq_2026/data/node/1/ad7606"
}
```

后台日志同步出现：

```text
收到消息 topic=fengyan_daq_2026/data/node/1/ad7606 len=208
```

## 注意事项

- 不要把 WiFi 密码、token、私钥、API key 写入仓库。
- 当前 5G 模块未到，本文只验证 WiFi 链路。
- 4G/5G 相关自检失败在当前阶段是预期现象。
- 如果重新刷官方镜像，LoRa 一定会回到不可用状态，需要重新写入包含 UART3 resource DTB 的 boot。
- 不建议在 Windows NTFS 目录里完整编译 RK SDK；SDK 内存在路径长度、大小写和保留文件名问题。后续需要完整编译时建议使用 WSL2、Linux 虚拟机或原生 Linux。

