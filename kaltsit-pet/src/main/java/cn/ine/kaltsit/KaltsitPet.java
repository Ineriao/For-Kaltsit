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

    // 拖拽状态（参照 ArkPets isMouseDragging）
    private boolean isMouseDragging = false;
    private boolean isMouseDown     = false;
    private int     mouseButton     = 0;
    private int     mouseDeltaX     = 0;
    private int     mouseDeltaY     = 0;
    private int     lastDragDeltaX  = 0;

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
        applyWindowPos();
    }

    @Override
    public void render() {
        float delta = Math.min(Gdx.graphics.getDeltaTime(), 0.05f);

        // 参照 ArkPets render()：如果没有拖拽则正常物理模拟
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
            applyWindowPos();
        }

        BehaviorSystem.State bs = behavior.getCurrent();
        boolean lowFloor = (bs == BehaviorSystem.State.SIT || bs == BehaviorSystem.State.SLEEP);
        physics.setWorldArea(lowFloor ? screenH - taskbarH + 40 : screenH - taskbarH, screenW);

        behavior.update(delta);
        spine.render(batch, delta);

        // 方案B：每帧用全局鼠标位置检测穿透（不依赖 GLFW 事件）
        // 鼠标在凯尔希身上 → 关穿透（可交互）；在透明区域 → 开穿透（系统级真穿透，不框选）
        if (!isMouseDragging) {
            int[] cur = window.getCursorPos();   // 屏幕绝对坐标
            int[] win = window.getPosition();     // 窗口左上角屏幕坐标
            int localX = cur[0] - win[0];
            int localY = cur[1] - win[1];
            // isPixelSolid 接受窗口坐标（0=顶部），内部自己做 Y 翻转
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
        onMouseDown();
        return true; // 参照 ArkPets：返回 true 消费事件
    }

    @Override
    public boolean touchDragged(int screenX, int screenY, int pointer) {
        if (pointer > 0) return false;
        int dx = screenX - mouseX;
        int dy = screenY - mouseY;
        mouseDeltaX = dx;
        mouseDeltaY = dy;
        // 参照 ArkPets：累加方向一致的 delta
        lastDragDeltaX = dx * lastDragDeltaX <= 0 ? dx : lastDragDeltaX + dx;
        mouseX = screenX; mouseY = screenY;
        isMouseDragging = true;
        onMouseDrag();
        return false; // 参照 ArkPets：返回 false 不消费
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
            behavior.onTouch();
            System.out.println("[Touch] click x=" + mouseX + " y=" + mouseY);
        }
    }

    private void onMouseDrag() {
        if (mouseButton != com.badlogic.gdx.Input.Buttons.RIGHT) {
            float newX = physics.getX() + mouseDeltaX;
            float newY = physics.getY() - mouseDeltaY;
            physics.drag(Gdx.graphics.getDeltaTime(), newX, newY);
            applyWindowPos();
            if (Math.abs(lastDragDeltaX) >= 4)
                spine.setFacing((int) Math.signum(lastDragDeltaX));
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

    private void applyWindowPos() {
        int wx = (int) physics.getX();
        int wy = (int) (screenH - taskbarH - physics.getY() - Launcher.HEIGHT);
        window.setPosition(wx, wy);
    }

    public void onIpcCommand(String cmd) {
        Gdx.app.postRunnable(() -> {
            switch (cmd.trim()) {
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
