# 调试记录

本文档记录 RK3576 / KICKPI K7 开发中常用的调试方法。

## 串口调试

需要记录：

- 串口芯片：
- 串口设备名：
- 波特率：
- 数据位：
- 停止位：
- 校验位：

常见 Linux 串口连接方式：

```bash
sudo picocom -b 1500000 /dev/ttyUSB0
```

实际波特率以开发板文档为准。

## 网络调试

常用命令：

```bash
ip addr
ip route
ping <target-ip>
ssh root@<board-ip>
```

## 日志查看

常用命令：

```bash
dmesg
dmesg -w
journalctl -xe
```

## 设备树和驱动调试

常用检查点：

- 设备树节点是否启用：`status = "okay";`
- pinctrl 是否配置正确。
- 时钟、复位、电源域是否完整。
- 驱动是否编进内核或模块。
- `/proc/device-tree/` 中是否能看到节点。
- `dmesg` 中是否有 probe 成功或失败日志。
