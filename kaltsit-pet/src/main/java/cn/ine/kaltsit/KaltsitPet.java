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
        float usableH = screenH - taskbarH;
        physics.setWorldArea(usableH, screenW);
        // 初始位置：屏幕中央偏右，方便找到
        physics.setPosition(screenW / 2f, 0f);
        applyWindowPos();
        System.out.println("[KaltsitPet] 初始窗口位置: wx=" + (int)(screenW/2) +
            " wy=" + (int)(screenH - taskbarH - 0 - Launcher.HEIGHT));
    }

    @Override
    public void render() {
        // 参照 ArkPets：不清空主帧缓冲，由 LWJGL3 透明帧缓冲合成处理
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

        // Sit/Sleep 时地板下沉 40px，让脚部动画完整显示
        BehaviorSystem.State bs = behavior.getCurrent();
        boolean lowFloor = (bs == BehaviorSystem.State.SIT || bs == BehaviorSystem.State.SLEEP);
        float usableH = screenH - taskbarH;
        physics.setWorldArea(lowFloor ? usableH + 40 : usableH, screenW);

        behavior.update(delta);

        // SpineModel.render 内部管理 batch.begin/end
        spine.render(batch, delta);
    }

    /** 像素检测：传入 libGDX 屏幕坐标（0=左上），内部统一做 Y 翻转 */
    private boolean isMouseAtSolidPixel() {
        return spine.isPixelSolid(mouseX, Launcher.HEIGHT - mouseY - 1);
    }

    /** 更新鼠标穿透状态（参照 ArkPets updateWindow/setTransparentMode） */
    private void updatePassthrough() {
        boolean solid = isMouseAtSolidPixel();
        window.setMousePassthrough(!solid);
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
        // 参照 ArkPets onMouseMoved：每次鼠标移动更新穿透状态
        updatePassthrough();
        return false;
    }

    // 其他 InputProcessor 方法（空实现）
    @Override public boolean keyDown(int k)        { return false; }
    @Override public boolean keyUp(int k)          { return false; }
    @Override public boolean keyTyped(char c)      { return false; }
    @Override public boolean scrolled(float a, float b) { return false; }

    private void applyWindowPos() {
        int wx = (int) physics.getX();
        // physY=0 → 脚踩任务栏顶部，窗口底部在 screenH-taskbarH
        // physY增大 → 窗口往上移
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
