package cn.ine.kaltsit;

import com.badlogic.gdx.backends.lwjgl3.Lwjgl3Application;
import com.badlogic.gdx.backends.lwjgl3.Lwjgl3ApplicationConfiguration;
import com.badlogic.gdx.graphics.Color;

import java.net.URISyntaxException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashSet;
import java.util.Set;

public class Launcher {
    public static final String TITLE   = "KaltsitPet";
    public static final int    WIDTH   = 600;
    public static final int    HEIGHT  = 750;
    public static final int    FPS     = 120;

    private static final Path MODEL_DIRECTORY = Path.of(
            "spine", "SpineModel", "char_1052_kalts2", "Building",
            "build_char_1052_kalts2"
    );
    private static final Path ASSETS_DIRECTORY = resolveAssetsDirectory();

    public static final String SKEL_PATH = ASSETS_DIRECTORY.resolve(MODEL_DIRECTORY)
            .resolve("build_char_1052_kalts2.skel").toString();
    public static final String ATLAS_PATH = ASSETS_DIRECTORY.resolve(MODEL_DIRECTORY)
            .resolve("build_char_1052_kalts2.atlas").toString();

    // IPC 端口（与 Electron 通信）
    public static final int IPC_PORT = 8766;

    public static void main(String[] args) {
        if (!Files.isRegularFile(Path.of(SKEL_PATH)) || !Files.isRegularFile(Path.of(ATLAS_PATH))) {
            System.err.println("[Launcher] Spine 模型资源不完整: " + ASSETS_DIRECTORY);
            System.err.println("[Launcher] 请通过 KALTSIT_ASSETS_DIR 指定资源目录");
            return;
        }

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

    private static Path resolveAssetsDirectory() {
        Set<Path> candidates = new LinkedHashSet<>();
        addConfiguredDirectory(candidates, System.getenv("KALTSIT_ASSETS_DIR"));
        addConfiguredDirectory(candidates, System.getProperty("kaltsit.assets.dir"));

        addAncestorCandidates(candidates, Path.of("").toAbsolutePath().normalize());
        try {
            Path codeSource = Path.of(Launcher.class.getProtectionDomain()
                    .getCodeSource().getLocation().toURI()).toAbsolutePath().normalize();
            addAncestorCandidates(candidates, Files.isDirectory(codeSource) ? codeSource : codeSource.getParent());
        } catch (URISyntaxException ignored) {
        }

        for (Path candidate : candidates) {
            Path atlas = candidate.resolve(MODEL_DIRECTORY).resolve("build_char_1052_kalts2.atlas");
            if (Files.isRegularFile(atlas)) return candidate;
        }

        return candidates.stream().findFirst()
                .orElse(Path.of("assets").toAbsolutePath().normalize());
    }

    private static void addConfiguredDirectory(Set<Path> candidates, String value) {
        if (value == null || value.isBlank()) return;
        candidates.add(Path.of(value).toAbsolutePath().normalize());
    }

    private static void addAncestorCandidates(Set<Path> candidates, Path start) {
        Path current = start;
        for (int depth = 0; current != null && depth < 5; depth += 1) {
            candidates.add(current.resolve("assets").normalize());
            candidates.add(current.normalize());
            current = current.getParent();
        }
    }
}
