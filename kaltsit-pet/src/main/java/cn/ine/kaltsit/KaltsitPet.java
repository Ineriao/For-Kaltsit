package cn.ine.kaltsit;

import com.badlogic.gdx.ApplicationAdapter;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.InputProcessor;
import com.badlogic.gdx.backends.lwjgl3.Lwjgl3Graphics;
import com.badlogic.gdx.graphics.g2d.PolygonSpriteBatch;

public class KaltsitPet extends ApplicationAdapter implements InputProcessor {

    private SpineModel     spine;
    private BehaviorSystem behavior;
    private PhysicsPlane   physics;
    private WindowManager  window;
    private IpcServer      ipc;
    private PolygonSpriteBatch batch;

    private int   taskbarH = 48;
    private int   screenW, screenH;
    private int   mouseX = 0, mouseY = 0;

    // 拖拽状态
    private boolean isMouseDragging = false;
    private boolean isMouseDown     = false;
    private int     mouseButton     = 0;
    private int     mouseDeltaX     = 0;
    private int     mouseDeltaY     = 0;
    private int     lastDragDeltaX  = 0;

    // 拖拽起始记录
    private int   dragStartMouseX = 0, dragStartMouseY = 0;
    private float dragStartPhysX  = 0, dragStartPhysY  = 0;

    // 双击检测
    private long  lastClickTime = 0;

    // 参照 ArkPets：windowPosition 缓动插值，拖动时 setToEnd() 立刻跳到目标
    private TransitionVector2 windowPosition;

    @Override
    public void create() {
        batch    = new PolygonSpriteBatch();
        spine    = new SpineModel(Launcher.SKEL_PATH, Launcher.ATLAS_PATH);
        behavior = new BehaviorSystem(spine);
        physics  = new PhysicsPlane();
        window   = new WindowManager();
        ipc      = new IpcServer(Launcher.IPC_PORT, this);

        Gdx.input.setInputProcessor(this);

        window.attach((Lwjgl3Graphics) Gdx.graphics);
        window.setAlwaysOnTop(true);
        ipc.start();

        screenW  = Gdx.graphics.getDisplayMode().width;
        screenH  = Gdx.graphics.getDisplayMode().height;
        taskbarH = WindowManager.getTaskbarHeight();
        int bbW = Gdx.graphics.getBackBufferWidth();
        int bbH = Gdx.graphics.getBackBufferHeight();
        System.out.println("[KaltsitPet] screen=" + screenW + "x" + screenH + " taskbar=" + taskbarH);
        System.out.println("[KaltsitPet] backbuffer=" + bbW + "x" + bbH + " window=" + Launcher.WIDTH + "x" + Launcher.HEIGHT);

        physics.setObjSize(Launcher.WIDTH, Launcher.HEIGHT);
        physics.setWorldArea(screenH - taskbarH, screenW);
        physics.setPosition(screenW / 2f, 0f);

        // 参照 ArkPets：windowPosition 缓动插值器（0.1s 过渡）
        windowPosition = new TransitionVector2(EasingFunction.EASE_OUT_SINE, 0.1f);
        windowPosition.reset(physics.getX(), getWindowY());
        windowPosition.setToEnd();
        applyWindowPos();
    }

    @Override
    public void render() {
        float delta = Math.min(Gdx.graphics.getDeltaTime(), 0.05f);

        if (!isMouseDragging) {
            if (behavior.isMoving()) {
                int dir = behavior.getMoveDir();
                float newX = Math.max(0, Math.min(screenW - Launcher.WIDTH,
                        physics.getX() + PhysicsPlane.MOVE_SPEED * dir * delta));
                physics.drag(delta, newX, physics.getY());
                spine.setFacing(dir);
            } else {
                physics.update(delta);
            }
        }

        // 每帧都根据物理坐标更新窗口位置（不管是否拖动）
        window.setPosition((int) physics.getX(),
                (int) (screenH - taskbarH - physics.getY() - Launcher.HEIGHT));

        BehaviorSystem.State bs = behavior.getCurrent();
        boolean lowFloor = (bs == BehaviorSystem.State.SIT || bs == BehaviorSystem.State.SLEEP);
        physics.setWorldArea(lowFloor ? screenH - taskbarH + 40 : screenH - taskbarH, screenW);

        behavior.update(delta);
        spine.render(batch, delta);

        // 穿透：拖动中强制关闭，否则按像素检测
        if (isMouseDragging) {
            window.setMousePassthrough(false);
        } else {
            int[] cur = window.getCursorPos();
            int[] win = window.getPosition();
            int localX = cur[0] - win[0];
            int localY = cur[1] - win[1];
            boolean solid = (localX >= 0 && localY >= 0
                    && localX < Launcher.WIDTH && localY < Launcher.HEIGHT
                    && spine.isPixelSolid(localX, localY));
            window.setMousePassthrough(!solid);
        }
    }

    // ── 像素检测（参照 ArkPets isMouseAtSolidPixel）──────────────
    private boolean isMouseAtSolidPixel() {
        // ArkPets: cha.getPixel(getMouseX(), cha.camera.getHeight() - getMouseY() - 1)
        return spine.isPixelSolid(mouseX, Launcher.HEIGHT - mouseY - 1);
    }

    // ── InputProcessor（严格参照 InputApplicationAdaptor）────────

    @Override
    public boolean touchDown(int screenX, int screenY, int pointer, int button) {
        if (pointer > 0) return false;
        mouseX = screenX; mouseY = screenY;
        mouseDeltaX = 0; lastDragDeltaX = 0;
        mouseButton = button;
        isMouseDown = true;
        // 起始坐标用 GetCursorPos（屏幕绝对坐标），与 onMouseDrag 保持一致
        int[] cur = window.getCursorPos();
        dragStartMouseX = cur[0];
        dragStartMouseY = cur[1];
        int[] winPos = window.getPosition();
        dragStartPhysX  = winPos[0];
        dragStartPhysY  = winPos[1];
        onMouseDown();
        return true;
    }

    @Override
    public boolean touchDragged(int screenX, int screenY, int pointer) {
        if (pointer > 0) return false;
        int dx = screenX - mouseX;
        int dy = screenY - mouseY;
        mouseDeltaX = dx;
        mouseDeltaY = dy;
        lastDragDeltaX = dx * lastDragDeltaX <= 0 ? dx : lastDragDeltaX + dx;
        mouseX = screenX; mouseY = screenY;
        isMouseDragging = true;
        onMouseDrag();
        return false;
    }

    @Override
    public boolean touchUp(int screenX, int screenY, int pointer, int button) {
        if (pointer > 0) return false;
        mouseX = screenX; mouseY = screenY;
        isMouseDown = false;
        onMouseUp();
        isMouseDragging = false;
        return false; // 参照 ArkPets
    }

    @Override
    public boolean mouseMoved(int screenX, int screenY) {
        mouseX = screenX; mouseY = screenY;
        onMouseMoved();
        return true; // 参照 ArkPets：返回 true
    }

    // ── 鼠标事件处理（参照 ArkPets onMouseDown/Drag/Up/Moved）────

    private void onMouseDown() {
        // 穿透已由 render() 全局检测处理；能收到事件说明在不透明区域
        if (mouseButton == com.badlogic.gdx.Input.Buttons.LEFT) {
            long now = System.currentTimeMillis();
            if (now - lastClickTime < 400) {
                // 双击：通知 Electron 展开对话界面
                IpcClient.send("open_chat");
                System.out.println("[Touch] double-click → open_chat");
            } else {
                behavior.onTouch();
                System.out.println("[Touch] click x=" + mouseX + " y=" + mouseY);
            }
            lastClickTime = now;
        }
    }

    private void onMouseDrag() {
        if (mouseButton != com.badlogic.gdx.Input.Buttons.RIGHT) {
            // 用全局鼠标坐标（GetCursorPos），不用 GLFW 窗口内坐标
            // GLFW 坐标在鼠标移出窗口时会被 clip，导致抖动
            int[] cur = window.getCursorPos();
            int totalDx = cur[0] - dragStartMouseX;
            int totalDy = cur[1] - dragStartMouseY;
            int newWinX = (int) dragStartPhysX + totalDx;
            int newWinY = (int) dragStartPhysY + totalDy;
            window.setPosition(newWinX, newWinY);
            physics.setPosition((float) newWinX,
                    screenH - taskbarH - newWinY - Launcher.HEIGHT);
        }
    }

    private void onMouseUp() {
        // 穿透由 render() 处理，这里无需转发
    }

    private void onMouseMoved() {
        // 穿透由 render() 全局检测处理，这里无需转发
    }

    // ── 空实现 ────────────────────────────────────────────────────
    @Override public boolean keyDown(int k)             { return false; }
    @Override public boolean keyUp(int k)               { return false; }
    @Override public boolean keyTyped(char c)           { return false; }
    @Override public boolean scrolled(float a, float b) { return false; }

    /** 参照 ArkPets：物理坐标 → 窗口 Y 坐标 */
    private float getWindowY() {
        return screenH - taskbarH - physics.getY() - Launcher.HEIGHT;
    }

    /** 参照 ArkPets updateWindow：用 windowPosition 插值后的位置应用到窗口 */
    private void applyWindowPos() {
        int wx = (int) windowPosition.now().x;
        int wy = (int) windowPosition.now().y;
        window.setPosition(wx, wy);
    }

    public void onIpcCommand(String cmd) {
        Gdx.app.postRunnable(() -> {
            String command = cmd.trim();
            if (command.startsWith("intent:")) {
                String[] parts = command.split(":", 5);
                if (parts.length != 5) return;
                try {
                    behavior.onExternalIntent(parts[4], parts[1], parts[2], Float.parseFloat(parts[3]));
                } catch (NumberFormatException ignored) {
                    System.err.println("[Behavior] 无效强度: " + parts[3]);
                }
                return;
            }
            if (command.startsWith("action:")) {
                behavior.onExternalAction(command.substring("action:".length()));
                return;
            }
            if (command.startsWith("lipsync:")) {
                try {
                    spine.setLipSync(Float.parseFloat(command.substring("lipsync:".length())));
                } catch (NumberFormatException ignored) {
                    spine.setLipSync(0f);
                }
                return;
            }
            switch (command) {
                case "show"  -> window.setVisible(true);
                case "hide"  -> window.setVisible(false);
                case "quit"  -> Gdx.app.exit();
                case "touch" -> behavior.onTouch();
            }
        });
    }

    @Override
    public void dispose() {
        batch.dispose();
        spine.dispose();
        ipc.stop();
    }
}
