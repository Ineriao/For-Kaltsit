package cn.ine.kaltsit;

import java.io.*;
import java.net.*;

/** TCP Socket 客户端，向 Electron 发送指令；Electron 未运行时自动启动 */
public class IpcClient {

    private static final int    ELECTRON_PORT = 8767;
    // 打包后 Electron exe 与 kaltsit-pet.jar 同目录
    private static final String ELECTRON_EXE  = "kaltsit-chat.exe";
    private static volatile boolean electronStarting = false;

    /** 向 Electron 发送指令；若未连接则先启动 Electron */
    public static void send(String cmd) {
        new Thread(() -> {
            if (!tryConnect(cmd)) {
                // Electron 未运行，启动后重试
                if (!electronStarting) {
                    electronStarting = true;
                    startElectron();
                    for (int i = 0; i < 16; i++) {
                        try { Thread.sleep(500); } catch (InterruptedException ignored) {}
                        if (tryConnect(cmd)) { electronStarting = false; return; }
                    }
                    electronStarting = false;
                    System.err.println("[IpcClient] Electron 启动超时");
                }
            }
        }, "ipc-client").start();
    }

    private static boolean tryConnect(String cmd) {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress("127.0.0.1", ELECTRON_PORT), 500);
            new PrintWriter(socket.getOutputStream(), true).println(cmd);
            System.out.println("[IpcClient] 发送: " + cmd);
            return true;
        } catch (IOException e) {
            return false;
        }
    }

    private static void startElectron() {
        try {
            String jarPath = IpcClient.class.getProtectionDomain()
                    .getCodeSource().getLocation().getPath();
            File exe = new File(new File(jarPath).getParent(), ELECTRON_EXE);
            if (!exe.exists()) {
                System.err.println("[IpcClient] Electron 未找到: " + exe.getAbsolutePath()
                        + "（开发模式请手动启动 Electron）");
                return;
            }
            new ProcessBuilder(exe.getAbsolutePath())
                    .directory(exe.getParentFile()).start();
            System.out.println("[IpcClient] 已启动 Electron: " + exe.getAbsolutePath());
        } catch (Exception e) {
            System.err.println("[IpcClient] 启动 Electron 失败: " + e.getMessage());
        }
    }
}
