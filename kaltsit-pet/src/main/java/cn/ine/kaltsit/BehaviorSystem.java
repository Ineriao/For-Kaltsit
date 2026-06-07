package cn.ine.kaltsit;

import java.util.List;
import java.util.Random;

/**
 * 行为状态机：管理 Idle/Sit/Sleep/Move/Special 动画切换
 * 按概率权重随机切换，点击触发特定动画后自动返回
 */
public class BehaviorSystem {

    public enum State { RELAX, SIT, SLEEP, MOVE_L, MOVE_R, SPECIAL, TOUCH }

    // RELAX 占绝大多数，其他偶尔穿插
    private static final float[] WEIGHTS = {
        55f,  // RELAX
        10f,  // SIT
        6f,   // SLEEP
        12f,  // MOVE_L
        12f,  // MOVE_R
        5f,   // SPECIAL
        0f    // TOUCH
    };

    private static final String[] ANIM_KEYS = {
        "Relax",    // RELAX
        "Sit",      // SIT
        "Sleep",    // SLEEP
        "Move",     // MOVE_L
        "Move",     // MOVE_R
        "Special",  // SPECIAL
        "Interact", // TOUCH
    };

    private static final float[] DUR_MIN = { 10f, 8f, 15f, 3f, 3f, 4f, 3f };
    private static final float[] DUR_MAX = { 25f, 20f, 40f, 8f, 8f, 8f, 5f };

    private final SpineModel spine;
    private final Random     rng = new Random();
    private State  current   = State.RELAX;
    private float  stateTimer = 0f;
    private float  stateDuration = 10f;
    // 移动方向（物理层使用）
    private int    moveDir = 0;
    private boolean touchPending = false;

    public BehaviorSystem(SpineModel spine) {
        this.spine = spine;
        printAvailableAnims();
        enterState(State.RELAX);  // 默认从 Relax 开始
    }

    private void printAvailableAnims() {
        List<String> names = spine.getAnimationNames();
        System.out.println("[Behavior] 可用动画: " + names);
    }

    public void update(float delta) {
        if (touchPending) {
            touchPending = false;
            enterState(State.TOUCH);
            return;
        }
        stateTimer += delta;
        if (stateTimer >= stateDuration) {
            // TOUCH 结束后回 IDLE
            if (current == State.TOUCH) {
                enterState(State.RELAX);
            } else {
                enterState(nextState());
            }
        }
    }

    public void onTouch() {
        touchPending = true;
    }

    /** 当前移动方向：-1 左，0 静止，+1 右 */
    public int getMoveDir() {
        return (current == State.MOVE_L) ? -1 : (current == State.MOVE_R) ? 1 : 0;
    }

    /** 当前状态是否正在移动 */
    public boolean isMoving() {
        return current == State.MOVE_L || current == State.MOVE_R;
    }

    public State getCurrent() { return current; }

    private void enterState(State s) {
        current    = s;
        stateTimer = 0f;
        stateDuration = DUR_MIN[s.ordinal()] +
                        rng.nextFloat() * (DUR_MAX[s.ordinal()] - DUR_MIN[s.ordinal()]);

        String key  = ANIM_KEYS[s.ordinal()];
        boolean loop = (s != State.TOUCH && s != State.SPECIAL);

        if (s == State.TOUCH || s == State.SPECIAL) {
            spine.playAnimation(key, false);
            spine.queueAnimation("Relax", true);
        } else {
            spine.playAnimation(key, loop);
        }
        System.out.println("[Behavior] -> " + s + " (" + String.format("%.1f", stateDuration) + "s)");
    }

    private State nextState() {
        float total = 0;
        for (int i = 0; i < WEIGHTS.length - 1; i++) total += WEIGHTS[i];
        float r = rng.nextFloat() * total;
        float acc = 0;
        for (int i = 0; i < WEIGHTS.length - 1; i++) {
            acc += WEIGHTS[i];
            if (r < acc) return State.values()[i];
        }
        return State.RELAX;
    }
}
