package cn.ine.kaltsit;

import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.graphics.OrthographicCamera;
import com.badlogic.gdx.graphics.Pixmap;
import com.badlogic.gdx.graphics.g2d.PolygonSpriteBatch;
import com.badlogic.gdx.graphics.g2d.TextureAtlas;
import com.badlogic.gdx.graphics.glutils.FrameBuffer;
import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.utils.ScreenUtils;
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

    // FBO 用于像素检测
    private final FrameBuffer        fbo;
    private final OrthographicCamera fboCamera;
    private final PolygonSpriteBatch fboBatch;

    // 主帧缓冲摄像机
    private final OrthographicCamera mainCamera;

    private final int W = Launcher.WIDTH;
    private final int H = Launcher.HEIGHT;

    public SpineModel(String skelPath, String atlasPath) {
        FileHandle atlasFile = new FileHandle(new File(atlasPath));
        FileHandle skelFile  = new FileHandle(new File(skelPath));

        atlas = new TextureAtlas(atlasFile);
        SkeletonBinary bin = new SkeletonBinary(atlas);
        bin.setScale(0.35f);
        skelData = bin.readSkeletonData(skelFile);

        skeleton = new Skeleton(skelData);
        skeleton.setPosition(W / 2f, 0f);  // 脚踩 mainCamera 底部(y=0)
        skeleton.updateWorldTransform();

        AnimationStateData asd = new AnimationStateData(skelData);
        asd.setDefaultMix(0.2f);
        animState = new AnimationState(asd);

        renderer = new SkeletonRenderer();
        renderer.setPremultipliedAlpha(false);

        // 主帧缓冲摄像机：(0,0)=左下角，视野 [0,W]x[0,H]
        mainCamera = new OrthographicCamera(W, H);
        mainCamera.position.set(W / 2f, H / 2f, 0);
        mainCamera.update();

        // FBO 摄像机（与主摄像机相同）
        fboCamera = new OrthographicCamera(W, H);
        fboCamera.position.set(W / 2f, H / 2f, 0);
        fboCamera.update();
        fbo      = new FrameBuffer(Pixmap.Format.RGBA8888, W, H, false);
        fboBatch = new PolygonSpriteBatch();

        System.out.println("[SpineModel] 可用动画: " + getAnimationNames());
        playAnimation("Relax", true);
    }

    public void playAnimation(String name, boolean loop) {
        Animation anim = skelData.findAnimation(name);
        if (anim != null) { animState.setAnimation(0, name, loop); return; }
        for (Animation a : skelData.getAnimations()) {
            if (a.getName().toLowerCase().contains(name.toLowerCase())) {
                animState.setAnimation(0, a.getName(), loop); return;
            }
        }
        if (!skelData.getAnimations().isEmpty())
            animState.setAnimation(0, skelData.getAnimations().first().getName(), true);
    }

    public void queueAnimation(String name, boolean loop) {
        try { animState.addAnimation(0, name, loop, 0); }
        catch (Exception e) { playAnimation(name, loop); }
    }

    public void setFacing(int dir) {
        if (dir == 0) return;
        skeleton.setScaleX(dir > 0 ? Math.abs(skeleton.getScaleX()) : -Math.abs(skeleton.getScaleX()));
    }

    /**
     * 直接渲染到主帧缓冲（透明背景），同时渲染到 FBO 用于像素检测。
     * 不在主帧缓冲里 glClear——由 LWJGL3 透明帧缓冲合成处理。
     */
    public void render(PolygonSpriteBatch screenBatch, float delta) {
        animState.update(delta);
        animState.apply(skeleton);
        skeleton.updateWorldTransform();

        // Pass 1：FBO（仅用于像素检测）
        fbo.begin();
        ScreenUtils.clear(0, 0, 0, 0, true);
        fboBatch.setProjectionMatrix(fboCamera.combined);
        fboBatch.begin();
        renderer.draw(fboBatch, skeleton);
        fboBatch.end();
        fbo.end();

        // Pass 2：清空主帧缓冲再渲染（清除残影）
        ScreenUtils.clear(0, 0, 0, 0, true);
        screenBatch.setProjectionMatrix(mainCamera.combined);
        screenBatch.begin();
        renderer.draw(screenBatch, skeleton);
        screenBatch.end();
    }

    /** 像素检测：从 FBO 读取，Y 轴翻转 */
    public boolean isPixelSolid(int x, int y) {
        if (x < 0 || y < 0 || x >= W || y >= H) return false;
        try {
            fbo.begin();
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
