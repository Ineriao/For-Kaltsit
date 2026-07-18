package cn.ine.kaltsit;

import java.io.*;
import java.net.*;

/** TCP Socket 服务器，监听 Electron 的指令 */
public class IpcServer {

    private final int        port;
    private final KaltsitPet pet;
    private ServerSocket     server;
    private Thread           thread;
    private volatile boolean running = false;

    public IpcServer(int port, KaltsitPet pet) {
        this.port = port;
        this.pet  = pet;
    }

    public void start() {
        running = true;
        thread  = new Thread(() -> {
            try {
                server = new ServerSocket();
                server.bind(new InetSocketAddress("127.0.0.1", port));
                System.out.println("[IPC] 监听端口 " + port);
                while (running) {
                    Socket client = server.accept();
                    new Thread(() -> handleClient(client)).start();
                }
            } catch (IOException e) {
                if (running) System.err.println("[IPC] 服务器错误: " + e.getMessage());
            }
        }, "ipc-server");
        thread.setDaemon(true);
        thread.start();
    }

    private void handleClient(Socket client) {
        try (client;
             BufferedReader r = new BufferedReader(new InputStreamReader(client.getInputStream()));
             PrintWriter writer = new PrintWriter(client.getOutputStream(), true)) {
            String line;
            while ((line = r.readLine()) != null) {
                System.out.println("[IPC] 收到指令: " + line);
                if ("ping".equals(line.trim())) writer.println("kaltsit-pet");
                else pet.onIpcCommand(line);
            }
        } catch (IOException e) {
            System.err.println("[IPC] 客户端断开: " + e.getMessage());
        }
    }

    public void stop() {
        running = false;
        try { if (server != null) server.close(); } catch (IOException ignored) {}
    }
}
