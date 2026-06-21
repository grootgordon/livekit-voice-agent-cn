pluginManagement {
    repositories {
        // 国内镜像优先（本网络下 dl.google.com / repo1.maven.org 间歇不可达）
        maven("https://maven.aliyun.com/repository/google")
        maven("https://maven.aliyun.com/repository/public")
        maven("https://maven.aliyun.com/repository/gradle-plugin")
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        maven("https://maven.aliyun.com/repository/google")
        maven("https://maven.aliyun.com/repository/public")
        google()
        mavenCentral()
        // livekit-android 传递依赖 com.github.davidliu:audioswitch 仅在 jitpack
        maven("https://jitpack.io")
    }
}

rootProject.name = "agent-android"
include(":app")
