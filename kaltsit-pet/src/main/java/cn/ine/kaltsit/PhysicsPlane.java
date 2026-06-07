package cn.ine.kaltsit;

/** 封装 Ark-Pets 原版 Plane，使用原始物理参数 */
public class PhysicsPlane {

    public final Plane plane;

    // 与 ArkPetsConfigDefault.json 一致
    public static final float GRAVITY_ACC     = 800f;
    public static final float AIR_FRICTION    = 100f;
    public static final float STATIC_FRICTION = 500f;
    public static final float SPEED_LIMIT_X   = 1000f;
    public static final float SPEED_LIMIT_Y   = 1000f;
    public static final float RESILIENCE      = 0f;
    public static final float MOVE_SPEED      = 60f;

    public PhysicsPlane() {
        plane = new Plane();
        plane.setGravity(GRAVITY_ACC);
        plane.setResilience(RESILIENCE);
        plane.setFrict(AIR_FRICTION, STATIC_FRICTION);
        plane.setSpeedLimit(SPEED_LIMIT_X, SPEED_LIMIT_Y);
    }

    public void setObjSize(float w, float h) {
        plane.setObjSize(w, h);
    }

    /**
     * 设置世界区域。
     * 坐标系约定：physY=0 表示脚踩在任务栏顶部，向上为正。
     * 对应 Plane 内部：bottom=0（地板），top=可用屏幕高度。
     */
    public void setWorldArea(float usableHeight, float screenW) {
        plane.world.clear();
        // Plane: left, right, top, bottom（top > bottom）
        plane.world.add(new Plane.RectArea(0, screenW, usableHeight, 0));
    }

    public void update(float delta) {
        plane.updatePosition(delta);
    }

    public void setPosition(float x, float y) {
        plane.changePosition(0, x, y);
    }

    public void drag(float deltaTime, float x, float y) {
        plane.changePosition(deltaTime, x, y);
    }

    public float getX() { return plane.getX(); }
    public float getY() { return plane.getY(); }
    public boolean isDropping() { return plane.getDropping(); }
    public boolean isDropped()  { return plane.getDropped(); }
}
