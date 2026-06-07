package cn.ine.kaltsit;

import com.badlogic.gdx.backends.lwjgl3.Lwjgl3Graphics;
import com.sun.jna.Native;
import com.sun.jna.platform.win32.User32;
import com.sun.jna.platform.win32.WinDef.HWND;
import com.sun.jna.platform.win32.WinUser;
import org.lwjgl.glfw.GLFW;

/** 窗口管理：GLFW 透明 + Win32 置顶 + 像素级点击穿透 */
public class WindowManager {

    private long   glfwHandle = 0;
    private HWND   hWnd       = null;
    private boolean passthrough = false;

    private static final int WS_EX_TOPMOST    = 0x00000008;
    private static final int WS_EX_TOOLWINDOW = 0x00000080;
    private static final int WS_EX_LAYERED    = 0x00080000;

    public void attach(Lwjgl3Graphics graphics) {
        glfwHandle = graphics.getWindow().getWindowHandle();
        // 通过窗口标题找到 HWND
        hWnd = User32.INSTANCE.FindWindow(null, Launcher.TITLE);
        System.out.println("[Window] HWND=" + hWnd + ", GLFW=" + glfwHandle);
    }

    /** 设置鼠标穿透（透明像素不响应鼠标） */
    public void setMousePassthrough(boolean enable) {
        if (glfwHandle == 0 || enable == passthrough) return;
        passthrough = enable;
        GLFW.glfwSetWindowAttrib(glfwHandle, GLFW.GLFW_MOUSE_PASSTHROUGH, enable ? 1 : 0);
    }

    private static final HWND HWND_TOPMOST  = new HWND(new com.sun.jna.Pointer(-1));
    private static final HWND HWND_NOTOPMOST = new HWND(new com.sun.jna.Pointer(-2));
    private static final int  SWP_FLAGS = WinUser.SWP_NOSIZE | WinUser.SWP_NOMOVE | WinUser.SWP_NOACTIVATE;

    /** 初始化窗口层级：高于任务栏但低于普通窗口 */
    public void setAlwaysOnTop(boolean enable) {
        if (hWnd == null) return;
        if (enable) {
            // 先设 TOPMOST 确保在任务栏上方
            User32.INSTANCE.SetWindowPos(hWnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_FLAGS);
            // 再立即降为 NOTOPMOST，这样普通窗口激活后会挡住凯尔希
            User32.INSTANCE.SetWindowPos(hWnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_FLAGS);
        } else {
            User32.INSTANCE.SetWindowPos(hWnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_FLAGS);
        }
        // 不在任务栏显示
        int style = User32.INSTANCE.GetWindowLong(hWnd, WinUser.GWL_EXSTYLE);
        style |= WS_EX_TOOLWINDOW;
        style &= ~0x00040000;
        User32.INSTANCE.SetWindowLong(hWnd, WinUser.GWL_EXSTYLE, style);
    }

    /** 设置窗口位置（不强制置顶） */
    public void setPosition(int x, int y) {
        if (hWnd == null) return;
        User32.INSTANCE.SetWindowPos(hWnd, HWND_NOTOPMOST, x, y,
                Launcher.WIDTH, Launcher.HEIGHT, WinUser.SWP_NOACTIVATE);
    }

    /** 获取当前窗口位置 */
    public int[] getPosition() {
        int[] x = new int[1], y = new int[1];
        GLFW.glfwGetWindowPos(glfwHandle, x, y);
        return new int[]{ x[0], y[0] };
    }

    /** 获取 Windows 任务栏高度（动态） */
    public static int getTaskbarHeight() {
        try {
            com.sun.jna.platform.win32.WinDef.RECT rect = new com.sun.jna.platform.win32.WinDef.RECT();
            com.sun.jna.platform.win32.WinDef.HWND taskbar = User32.INSTANCE.FindWindow("Shell_TrayWnd", null);
            if (taskbar != null) {
                User32.INSTANCE.GetWindowRect(taskbar, rect);
                return rect.bottom - rect.top;
            }
        } catch (Exception e) {
            System.err.println("[Window] 获取任务栏高度失败: " + e.getMessage());
        }
        return 48;
    }

    public void setVisible(boolean visible) {
        if (glfwHandle == 0) return;
        if (visible) GLFW.glfwShowWindow(glfwHandle);
        else         GLFW.glfwHideWindow(glfwHandle);
    }
}
