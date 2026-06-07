package cn.ine.kaltsit;

import java.io.*;
import java.net.*;

/** TCP Socket 客户端，向 Electron 发送指令 */
public class IpcClient {

    private static final int ELECTRON_PORT = 8767; // Electron 监听的端口

    /**
     * 向 Electron 发送一条指令（单次短连接）
     * @param cmd 指令字符串，如 "open_chat"
     */
    public static void send(String cmd) {
        new Thread(() -> {
            try (Socket socket = new Socket("127.0.0.1", ELECTRON_PORT);
                 PrintWriter w = new PrintWriter(socket.getOutputStream(), true)) {
                w.println(cmd);
                System.out.println("[IpcClient] 发送: " + cmd);
            } catch (IOException e) {
                // Electron 未运行时静默失败
                System.err.println("[IpcClient] 发送失败（Electron 未连接）: " + e.getMessage());
            }
        }, "ipc-client").start();
    }
}
