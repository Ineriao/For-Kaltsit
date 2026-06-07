package cn.ine.kaltsit;

import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.graphics.GL20;
import com.badlogic.gdx.graphics.OrthographicCamera;
import com.badlogic.gdx.graphics.Pixmap;
import com.badlogic.gdx.graphics.g2d.PolygonSpriteBatch;
import com.badlogic.gdx.graphics.g2d.TextureAtlas;
import com.badlogic.gdx.graphics.glutils.FrameBuffer;
import com.badlogic.gdx.files.FileHandle;
import com.esotericsoftware.spine.*;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

public class SpineModel {

    private final SkeletonRenderer renderer;
    private final Skeleton          skeleton;
    private final AnimationState    animState;
    private final SkeletonData      skelData;
    private final TextureAtlas      atlas;

    // FBO：离屏渲染，用于像素级点击穿透
    private FrameBuffer         fbo;
    private OrthographicCamera  fboCamera;
    private PolygonSpriteBatch  fboBatch;

    private final int W = Launcher.WIDTH;
    private final int H = Launcher.HEIGHT;

    public SpineModel(String skelPath, String atlasPath) {
        FileHandle atlasFile = new FileHandle(new File(atlasPath));
        FileHandle skelFile  = new FileHandle(new File(skelPath));

        atlas = new TextureAtlas(atlasFile);
        SkeletonBinary bin = new SkeletonBinary(atlas);
        bin.setScale(0.35f);
        skelData = bin.readSkeletonData(skelFile);

        skeleton  = new Skeleton(skelData);
        // fboCamera 中心在 (W/2, H/2)，摄像机看 Y=[-H/2, H/2]
        // 脚踩 FBO 底部 = Y = -H/2f
        skeleton.setPosition(W / 2f, -H / 2f);
        skeleton.updateWorldTransform();

        AnimationStateData asd = new AnimationStateData(skelData);
        asd.setDefaultMix(0.2f);
        animState = new AnimationState(asd);

        renderer = new SkeletonRenderer();
        renderer.setPremultipliedAlpha(false);

        // FBO 初始化
        fbo       = new FrameBuffer(Pixmap.Format.RGBA8888, W, H, false);
        fboCamera = new OrthographicCamera(W, H);
        fboCamera.position.set(W / 2f, H / 2f, 0);
        fboCamera.update();
        fboBatch  = new PolygonSpriteBatch();

        System.out.println("[SpineModel] 可用动画: " + getAnimationNames());
        playAnimation("Relax", true);
    }

    public void playAnimation(String name, boolean loop) {
        Animation anim = skelData.findAnimation(name);
        if (anim != null) {
            animState.setAnimation(0, name, loop);
            return;
        }
        // 模糊匹配
        for (Animation a : skelData.getAnimations()) {
            if (a.getName().toLowerCase().contains(name.toLowerCase())) {
                animState.setAnimation(0, a.getName(), loop);
                return;
            }
        }
        if (!skelData.getAnimations().isEmpty())
            animState.setAnimation(0, skelData.getAnimations().first().getName(), true);
    }

    public void queueAnimation(String name, boolean loop) {
        try { animState.addAnimation(0, name, loop, 0); }
        catch (Exception e) { playAnimation(name, loop); }
    }

    // 各动画状态的骨骼 Y 偏移
    private float skeletonOffsetY = 80f;

    public void setSkeletonOffsetY(float y) {
        skeletonOffsetY = y;
    }

    /** 设置朝向，dir > 0 朝右，dir < 0 朝左 */
    public void setFacing(int dir) {
        if (dir == 0) return;
        skeleton.setScaleX(dir > 0 ? Math.abs(skeleton.getScaleX()) : -Math.abs(skeleton.getScaleX()));
    }

    /**
     * 渲染到 FBO（离屏），同时把 FBO 内容 blit 到屏幕。
     * 渲染完后可以调 isPixelSolid 读 FBO 像素，坐标准确。
     */
    public void render(PolygonSpriteBatch screenBatch, float delta) {
        animState.update(delta);
        animState.apply(skeleton);
        skeleton.updateWorldTransform();

        // 1. 渲染到 FBO
        fbo.begin();
        Gdx.gl.glClearColor(0, 0, 0, 0);
        Gdx.gl.glClear(GL20.GL_COLOR_BUFFER_BIT);
        fboBatch.getProjectionMatrix().set(fboCamera.combined);
        fboBatch.begin();
        renderer.draw(fboBatch, skeleton);
        fboBatch.end();
        fbo.end();

        // 2. 把 FBO 贴到屏幕
        screenBatch.begin();
        screenBatch.draw(fbo.getColorBufferTexture(),
                0, 0, W, H,
                0, 0, W, H,
                false, true); // flipY
        screenBatch.end();
    }

    /**
     * 像素级点击穿透检测 — 读 FBO 像素，与 ArkPets 逻辑一致。
     * x,y 为窗口内坐标（0,0=左上角，Y向下）。
     */
    public boolean isPixelSolid(int x, int y) {
        if (x < 0 || y < 0 || x >= W || y >= H) return false;
        try {
            fbo.begin();
            // FBO Y 轴向上，窗口 Y 轴向下，需翻转
            Pixmap px = Pixmap.createFromFrameBuffer(x, H - y - 1, 1, 1);
            fbo.end();
            int pixel = px.getPixel(0, 0);
            px.dispose();
            return (pixel & 0xFF) > 10;
        } catch (Exception e) {
            return true;
        }
    }

    public List<String> getAnimationNames() {
        List<String> names = new ArrayList<>();
        for (Animation a : skelData.getAnimations()) names.add(a.getName());
        return names;
    }

    public void dispose() {
        fbo.dispose();
        fboBatch.dispose();
        atlas.dispose();
    }
}
