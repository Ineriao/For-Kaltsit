package cn.ine.kaltsit;

import java.io.File;
import java.io.IOException;
import java.io.PrintWriter;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URISyntaxException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashSet;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;

/** TCP Socket 客户端，向 Electron 发送指令；Electron 未运行时自动启动 */
public class IpcClient {

    private static final int ELECTRON_PORT = 8767;
    private static final String[] ELECTRON_EXE_NAMES = {"凯尔希.exe", "kaltsit-chat.exe"};
    private static final AtomicBoolean ELECTRON_STARTING = new AtomicBoolean(false);

    /** 向 Electron 发送指令；若未连接则先启动 Electron */
    public static void send(String cmd) {
        new Thread(() -> {
            if (!tryConnect(cmd) && ELECTRON_STARTING.compareAndSet(false, true)) {
                try {
                    if (!startElectron()) return;
                    for (int i = 0; i < 16; i++) {
                        try {
                            Thread.sleep(500);
                        } catch (InterruptedException error) {
                            Thread.currentThread().interrupt();
                            return;
                        }
                        if (tryConnect(cmd)) return;
                    }
                    System.err.println("[IpcClient] Electron 启动超时");
                } finally {
                    ELECTRON_STARTING.set(false);
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

    private static boolean startElectron() {
        try {
            File executable = resolveElectronExecutable();
            if (executable == null) {
                System.err.println("[IpcClient] Electron 未找到（开发模式请手动启动 Electron）");
                return false;
            }
            new ProcessBuilder(executable.getAbsolutePath())
                    .directory(executable.getParentFile()).start();
            System.out.println("[IpcClient] 已启动 Electron: " + executable.getAbsolutePath());
            return true;
        } catch (Exception e) {
            System.err.println("[IpcClient] 启动 Electron 失败: " + e.getMessage());
            return false;
        }
    }

    private static File resolveElectronExecutable() {
        String configured = System.getenv("KALTSIT_ELECTRON_EXE");
        if (configured != null && !configured.isBlank()) {
            File executable = new File(configured).getAbsoluteFile();
            if (executable.isFile()) return executable;
        }

        Set<Path> directories = new LinkedHashSet<>();
        addAncestorDirectories(directories, Path.of("").toAbsolutePath().normalize());
        try {
            Path codeSource = Path.of(IpcClient.class.getProtectionDomain()
                    .getCodeSource().getLocation().toURI()).toAbsolutePath().normalize();
            addAncestorDirectories(directories, Files.isDirectory(codeSource) ? codeSource : codeSource.getParent());
        } catch (URISyntaxException ignored) {
        }

        for (Path directory : directories) {
            for (String name : ELECTRON_EXE_NAMES) {
                File executable = directory.resolve(name).toFile();
                if (executable.isFile()) return executable;
            }
        }
        return null;
    }

    private static void addAncestorDirectories(Set<Path> directories, Path start) {
        Path current = start;
        for (int depth = 0; current != null && depth < 5; depth += 1) {
            directories.add(current);
            current = current.getParent();
        }
    }
}
