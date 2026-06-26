# K7 Linux 网关接口约定

本文档记录从旧 STM32 网关迁移到 K7 Linux 网关时必须保持一致的接口。旧工程参考路径：

- `1.网关/onenet_v1/USER/main.h`
- `1.网关/onenet_v1/HARDWARE/Scr/lora.c`
- `1.网关/onenet_v1/HARDWARE/Scr/wifi_cat1.c`

## 目标功能

K7 Linux 网关需要逐步复现旧 STM32 网关的核心功能：

1. 通过 LoRa E22 模块与节点板通信。
2. 解析节点板上报的 LoRa 数据帧。
3. 通过 4G/5G 或其他可用网络访问 MQTT broker。
4. 将节点数据上传到后台。

## K7 已验证硬件基线

交接文档记录的当前基线：

- K7 已刷好系统。
- `/dev/ttyS3` 已存在。
- UART3 运行时设备树状态为 `okay`。
- I2C7 运行时设备树状态为 `disabled`。
- UART3 本地回环已通过。
- E22-400T22D 已通过 UART3 返回配置响应。

已验证的 E22 读配置响应：

```text
TX_HEX= c10009
RX_LEN= 12
RX_HEX= c100090000006500170b0000
```

## LoRa 串口

K7 侧优先使用：

```text
/dev/ttyS3
```

E22 配置读取时使用：

```text
9600 8N1
```

E22 读配置命令：

```text
C1 00 09
```

## LoRa E22 参数

旧 STM32 网关中 `LoRaSetData` 的目标参数：

| 参数 | 值 |
| --- | --- |
| 模块地址 | `0x0000` |
| NetID | `0x00` |
| 串口波特率 | `9600` |
| 串口格式 | `8N1` |
| 空中速率 | `19.2K` |
| 数据分包 | `240 bytes` |
| RSSI | disabled |
| 软件切换 | disabled |
| 发射功率 | `22 dBm` |
| 信道 | `0x17`，对应 433 MHz |
| 传输模式 | 透明传输 |
| 中继 | disabled |
| LBT | disabled |
| WOR | TX，周期 2000 ms |

## LoRa 数据帧

旧网关当前使用的新帧格式：

```text
[NODE_ADDR][TYPE][LEN][PAYLOAD...][CRC_H][CRC_L]
```

字段说明：

| 字段 | 长度 | 说明 |
| --- | --- | --- |
| `NODE_ADDR` | 1 | 节点地址，从 1 开始 |
| `TYPE` | 1 | 数据类型 |
| `LEN` | 1 | payload 长度 |
| `PAYLOAD` | LEN | 类型相关载荷 |
| `CRC_H` | 1 | CRC 高字节 |
| `CRC_L` | 1 | CRC 低字节 |

CRC 使用 STM32 旧工程中的 CRC-16/MODBUS 参数：

| 参数 | 值 |
| --- | --- |
| polynomial | `0x8005` |
| init | `0xFFFF` |
| input inversion | byte |
| output inversion | enabled |

在 Linux 代码中按常见 CRC-16/MODBUS 算法实现，帧中按高字节、低字节存放。

## LoRa TYPE

| TYPE | 名称 | 说明 |
| --- | --- | --- |
| `0x01` | AD7606 | 8 通道原始值，payload 16 字节 |
| `0x02` | CAN | CAN 原始帧 |
| `0x03` | RS485 | Modbus 响应原始寄存器 |

### TYPE 0x01 AD7606

payload：

```text
CH1_H CH1_L ... CH8_H CH8_L
```

每通道为 big-endian signed int16。旧代码换算示例：

```text
mV = raw * 5000.0 / 32767.0
```

MQTT topic：

```text
fengyan_daq_2026/data/node/{node}/ad7606
```

payload 示例：

```json
{"ts":123456,"raw":"010110..."}
```

### TYPE 0x02 CAN

payload：

```text
CAN_ID_H CAN_ID_L DLC DATA0 ... DATA7
```

MQTT topic：

```text
fengyan_daq_2026/data/node/{node}/can
```

payload 示例：

```json
{"ts":123456,"id":"123","dlc":8,"data":"0102030405060708"}
```

### TYPE 0x03 RS485

payload 目前按 4 个 big-endian uint16 寄存器解析：

```text
REG0_H REG0_L ... REG3_H REG3_L
```

MQTT topic：

```text
fengyan_daq_2026/data/node/{node}/rs485
```

payload 示例：

```json
{"ts":123456,"voltage":2200,"current":120,"soc":90,"raw3":0}
```

## MQTT

旧工程当前配置：

| 项目 | 值 |
| --- | --- |
| broker | `broker.hivemq.com` |
| port | `1883` |
| client id | `GW001_fengyan` |
| username | 空 |
| password | 空 |
| topic prefix | `fengyan_daq_2026` |

K7 Linux 版本后续应优先使用系统网络能力，由 4G/5G/WiFi/以太网提供默认路由，再由应用层 MQTT 客户端连接 broker。
