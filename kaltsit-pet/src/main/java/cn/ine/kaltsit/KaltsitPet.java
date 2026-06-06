package cn.ine.kaltsit;

import com.badlogic.gdx.ApplicationAdapter;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.InputProcessor;
import com.badlogic.gdx.backends.lwjgl3.Lwjgl3Graphics;
import com.badlogic.gdx.graphics.GL20;
import com.badlogic.gdx.graphics.g2d.PolygonSpriteBatch;

public class KaltsitPet extends ApplicationAdapter implements InputProcessor {

    private SpineModel     spine;
    private BehaviorSystem behavior;
    private PhysicsPlane   physics;
    private WindowManager  window;
    private IpcServer      ipc;
    private PolygonSpriteBatch batch;

    private int  taskbarH = 48;
    private int  screenW, screenH;

    // 拖拽
    private boolean dragging = false;
    private int     dragStartX, dragStartY;
    private float   dragPhysX, dragPhysY;

    // 鼠标坐标（由 InputProcessor 更新）
    private int mouseX = 0, mouseY = 0;

    @Override
    public void create() {
        batch    = new PolygonSpriteBatch();
        spine    = new SpineModel(Launcher.SKEL_PATH, Launcher.ATLAS_PATH);
        behavior = new BehaviorSystem(spine);
        physics  = new PhysicsPlane();
        window   = new WindowManager();
        ipc      = new IpcServer(Launcher.IPC_PORT, this);

        // 注册输入处理器（ArkPets 同款）
        Gdx.input.setInputProcessor(this);

        window.attach((Lwjgl3Graphics) Gdx.graphics);
        window.setAlwaysOnTop(true);
        ipc.start();

        screenW  = Gdx.graphics.getDisplayMode().width;
        screenH  = Gdx.graphics.getDisplayMode().height;
        taskbarH = WindowManager.getTaskbarHeight();
        System.out.println("[KaltsitPet] screen=" + screenW + "x" + screenH + " taskbar=" + taskbarH);

        physics.setObjSize(Launcher.WIDTH, Launcher.HEIGHT);
        physics.setWorldArea(0, screenW, screenH, taskbarH);

        physics.setPosition(screenW - Launcher.WIDTH - 20f, taskbarH);
        applyWindowPos();
    }

    @Override
    public void render() {
        Gdx.gl.glClearColor(0, 0, 0, 0);
        Gdx.gl.glClear(GL20.GL_COLOR_BUFFER_BIT);

        float delta = Math.min(Gdx.graphics.getDeltaTime(), 0.05f);

        if (!dragging) {
            if (behavior.isMoving()) {
                int dir = behavior.getMoveDir();
                // drag 直接设定新位置，Plane 内部由此计算速度，不受摩擦干扰
                float newX = Math.max(0, Math.min(screenW - Launcher.WIDTH,
                        physics.getX() + PhysicsPlane.MOVE_SPEED * dir * delta));
                physics.drag(delta, newX, physics.getY());
                spine.setFacing(dir);
            } else {
                physics.update(delta);
            }
            applyWindowPos();
        }

        // Sit/Sleep 时地板下沉，applyWindowPos 也要跟着下移
        BehaviorSystem.State bs = behavior.getCurrent();
        boolean lowFloor = (bs == BehaviorSystem.State.SIT || bs == BehaviorSystem.State.SLEEP);
        physics.setWorldArea(0, screenW, screenH, lowFloor ? taskbarH - 40 : taskbarH);

        behavior.update(delta);

        // SpineModel.render 内部管理 batch.begin/end，直接调用
        spine.render(batch, delta);

        // 渲染完后读 FBO 像素，更新穿透状态
        boolean solid = spine.isPixelSolid(mouseX, mouseY);
        window.setMousePassthrough(!solid);
    }

    /** 像素检测 — 与 ArkPets 一致 */
    private boolean isMouseAtSolidPixel() {
        // mouseY 已经是 libGDX 坐标（0=顶部），Spine 渲染坐标 0=底部
        return spine.isPixelSolid(mouseX, Launcher.HEIGHT - mouseY - 1);
    }

    // ── InputProcessor ──────────────────────────────────────────

    @Override
    public boolean touchDown(int screenX, int screenY, int pointer, int button) {
        mouseX = screenX; mouseY = screenY;
        if (!isMouseAtSolidPixel()) return false; // 透明像素：穿透

        if (button == com.badlogic.gdx.Input.Buttons.LEFT) {
            dragging   = true;
            dragStartX = screenX; dragStartY = screenY;
            dragPhysX  = physics.getX(); dragPhysY = physics.getY();
            behavior.onTouch();
        }
        return true;
    }

    @Override
    public boolean touchDragged(int screenX, int screenY, int pointer) {
        mouseX = screenX; mouseY = screenY;
        if (!dragging) return false;

        float dx = screenX - dragStartX;
        float dy = -(screenY - dragStartY); // Y 轴翻转
        physics.drag(Gdx.graphics.getDeltaTime(), dragPhysX + dx, dragPhysY + dy);
        applyWindowPos();
        return true;
    }

    @Override
    public boolean touchUp(int screenX, int screenY, int pointer, int button) {
        mouseX = screenX; mouseY = screenY;
        dragging = false;
        return false;
    }

    @Override
    public boolean mouseMoved(int screenX, int screenY) {
        mouseX = screenX; mouseY = screenY;
        return false;
    }

    // 其他 InputProcessor 方法（空实现）
    @Override public boolean keyDown(int k)        { return false; }
    @Override public boolean keyUp(int k)          { return false; }
    @Override public boolean keyTyped(char c)      { return false; }
    @Override public boolean scrolled(float a, float b) { return false; }

    private void applyWindowPos() {
        int wx = (int) physics.getX();
        // physY=taskbarH 时窗口底部贴任务栏顶；physY<taskbarH 时窗口可超出到任务栏内（置顶可见）
        int wy = (int) (screenH - physics.getY() - Launcher.HEIGHT);
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
