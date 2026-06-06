package cn.ine.kaltsit;

/** 封装 Ark-Pets 原版 Plane，使用原始物理参数 */
public class PhysicsPlane {

    public final Plane plane;

    // 与 ArkPetsConfigDefault.json 一致
    public static final float GRAVITY_ACC       = 800f;
    public static final float AIR_FRICTION      = 100f;
    public static final float STATIC_FRICTION   = 500f;
    public static final float SPEED_LIMIT_X     = 1000f;
    public static final float SPEED_LIMIT_Y     = 1000f;
    public static final float RESILIENCE        = 0f;
    public static final float MOVE_SPEED = 60f;  // px/s，适中速度

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

    /** 设置世界区域（可移动边界），对应屏幕工作区 */
    public void setWorldArea(float left, float right, float top, float bottom) {
        plane.world.clear();
        plane.world.add(new Plane.RectArea(left, right, top, bottom));
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
