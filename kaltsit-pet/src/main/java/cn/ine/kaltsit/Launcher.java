package cn.ine.kaltsit;

import com.badlogic.gdx.backends.lwjgl3.Lwjgl3Application;
import com.badlogic.gdx.backends.lwjgl3.Lwjgl3ApplicationConfiguration;
import com.badlogic.gdx.graphics.Color;

public class Launcher {
    public static final String TITLE   = "KaltsitPet";
    public static final int    WIDTH   = 400;
    public static final int    HEIGHT  = 500;
    public static final int    FPS     = 30;

    // Spine 模型路径（Building 基建模式）
    public static final String SKEL_PATH  = "D:/Kal'tsit/SpineModel/char_1052_kalts2/Building/build_char_1052_kalts2/build_char_1052_kalts2.skel";
    public static final String ATLAS_PATH = "D:/Kal'tsit/SpineModel/char_1052_kalts2/Building/build_char_1052_kalts2/build_char_1052_kalts2.atlas";

    // IPC 端口（与 Electron 通信）
    public static final int IPC_PORT = 8766;

    public static void main(String[] args) {
        Lwjgl3ApplicationConfiguration cfg = new Lwjgl3ApplicationConfiguration();
        cfg.setTitle(TITLE);
        cfg.setWindowedMode(WIDTH, HEIGHT);
        cfg.setDecorated(false);
        cfg.setResizable(false);
        cfg.setTransparentFramebuffer(true);
        cfg.setInitialBackgroundColor(Color.CLEAR);
        cfg.setForegroundFPS(FPS);
        cfg.setIdleFPS(FPS);
        cfg.setInitialVisible(true);
        cfg.setWindowPosition(100, 100);

        new Lwjgl3Application(new KaltsitPet(), cfg);
    }
}
