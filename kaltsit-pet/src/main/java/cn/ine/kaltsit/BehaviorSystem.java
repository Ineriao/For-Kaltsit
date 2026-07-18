package cn.ine.kaltsit;

import java.util.List;
import java.util.Random;

/**
 * 行为状态机：管理 Idle/Sit/Sleep/Move/Special 动画切换
 * 按概率权重随机切换，点击触发特定动画后自动返回
 */
public class BehaviorSystem {

    public enum State { RELAX, SIT, SLEEP, MOVE_L, MOVE_R, SPECIAL, TOUCH }
    public enum Emotion { CALM, ALERT, FOCUSED, TIRED, DISPLEASED }
    public enum Mode { IDLE, CONVERSATION, READING, WORK, SLEEPING }

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
    private static final long ACTION_COOLDOWN_MS = 900L;
    private static final float INTENT_HOLD_SECONDS = 45f;

    private final SpineModel spine;
    private final Random     rng = new Random();
    private State  current   = State.RELAX;
    private float  stateTimer = 0f;
    private float  stateDuration = 10f;
    private Emotion emotion = Emotion.CALM;
    private Mode mode = Mode.IDLE;
    private float intensity = 0.2f;
    private float intentTimer = 0f;
    private long lastExternalActionAt = 0L;
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
        updateIntent(delta);
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
        emotion = Emotion.ALERT;
        mode = Mode.CONVERSATION;
        intensity = Math.max(intensity, 0.55f);
        intentTimer = INTENT_HOLD_SECONDS;
        touchPending = true;
    }

    public boolean onExternalAction(String action) {
        return onExternalIntent(action, emotion.name(), mode.name(), intensity);
    }

    public boolean onExternalIntent(
            String action,
            String emotionName,
            String modeName,
            float requestedIntensity
    ) {
        State target = switch (action) {
            case "RELAX" -> State.RELAX;
            case "SIT" -> State.SIT;
            case "SLEEP" -> State.SLEEP;
            case "MOVE_LEFT" -> State.MOVE_L;
            case "MOVE_RIGHT" -> State.MOVE_R;
            case "SPECIAL" -> State.SPECIAL;
            case "TOUCH" -> State.TOUCH;
            default -> null;
        };
        if (target == null) return false;

        try {
            emotion = Emotion.valueOf(emotionName);
            mode = Mode.valueOf(modeName);
        } catch (IllegalArgumentException error) {
            return false;
        }
        intensity = Math.max(0f, Math.min(requestedIntensity, 1f));
        intentTimer = INTENT_HOLD_SECONDS;

        long now = System.currentTimeMillis();
        if (target != State.TOUCH && now - lastExternalActionAt < ACTION_COOLDOWN_MS) return true;
        lastExternalActionAt = now;
        touchPending = false;
        enterState(target);
        return true;
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
    public Emotion getEmotion() { return emotion; }
    public Mode getMode() { return mode; }

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
        float[] weights = adjustedWeights();
        float total = 0;
        for (int i = 0; i < weights.length - 1; i++) total += weights[i];
        float r = rng.nextFloat() * total;
        float acc = 0;
        for (int i = 0; i < weights.length - 1; i++) {
            acc += weights[i];
            if (r < acc) return State.values()[i];
        }
        return State.RELAX;
    }

    private void updateIntent(float delta) {
        if (intentTimer > 0f) {
            intentTimer -= delta;
            return;
        }
        mode = Mode.IDLE;
        if (emotion != Emotion.TIRED) emotion = Emotion.CALM;
        intensity += (0.2f - intensity) * Math.min(delta * 0.4f, 1f);
    }

    private float[] adjustedWeights() {
        float[] weights = WEIGHTS.clone();
        switch (mode) {
            case SLEEPING -> {
                weights[State.RELAX.ordinal()] = 15f;
                weights[State.SIT.ordinal()] = 20f;
                weights[State.SLEEP.ordinal()] = 65f;
                weights[State.MOVE_L.ordinal()] = 0f;
                weights[State.MOVE_R.ordinal()] = 0f;
                weights[State.SPECIAL.ordinal()] = 0f;
            }
            case READING, WORK -> {
                weights[State.RELAX.ordinal()] = 38f;
                weights[State.SIT.ordinal()] = 48f;
                weights[State.SLEEP.ordinal()] = emotion == Emotion.TIRED ? 10f : 2f;
                weights[State.MOVE_L.ordinal()] = 4f;
                weights[State.MOVE_R.ordinal()] = 4f;
                weights[State.SPECIAL.ordinal()] = 4f;
            }
            case CONVERSATION -> {
                weights[State.RELAX.ordinal()] = 52f;
                weights[State.SIT.ordinal()] = 18f;
                weights[State.SPECIAL.ordinal()] = 10f + intensity * 10f;
            }
            case IDLE -> { }
        }

        if (emotion == Emotion.ALERT || emotion == Emotion.DISPLEASED) {
            weights[State.MOVE_L.ordinal()] += 8f * intensity;
            weights[State.MOVE_R.ordinal()] += 8f * intensity;
            weights[State.SPECIAL.ordinal()] += 6f * intensity;
        } else if (emotion == Emotion.TIRED) {
            weights[State.SIT.ordinal()] += 12f;
            weights[State.SLEEP.ordinal()] += 14f;
            weights[State.MOVE_L.ordinal()] *= 0.35f;
            weights[State.MOVE_R.ordinal()] *= 0.35f;
        } else if (emotion == Emotion.FOCUSED) {
            weights[State.SIT.ordinal()] += 10f;
            weights[State.SPECIAL.ordinal()] += 4f;
        }
        return weights;
    }
}
