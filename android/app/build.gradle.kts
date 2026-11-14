import java.util.Properties
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
  alias(libs.plugins.android.application)
  alias(libs.plugins.jetbrains.kotlin.android)
  alias(libs.plugins.compose.compiler)
}

// Sign API address and key live in sign_talk/.env, which git ignores.
val signEnv: Map<String, String> =
    rootDir.resolve("../.env").takeIf { it.exists() }?.readLines().orEmpty()
        .mapNotNull { line -> line.split("=", limit = 2).takeIf { it.size == 2 }?.let { it[0].trim() to it[1].trim() } }
        .toMap()

val localProperties =
    Properties().apply {
      val file = rootDir.resolve("local.properties")
      if (file.exists()) file.inputStream().use { load(it) }
    }

android {
  namespace = "com.signtalk.app"
  compileSdk = 36

  defaultConfig {
    buildConfigField("String", "SIGN_API_URL", "\"${signEnv["SIGN_API_URL"] ?: ""}\"")
    buildConfigField("String", "SIGN_API_KEY", "\"${signEnv["SIGN_API_KEY"] ?: ""}\"")
    buildConfigField("String", "GLOVE_HOST", "\"${signEnv["GLOVE_HOST"] ?: ""}\"")
    applicationId = "com.signtalk.app"
    minSdk = 31
    targetSdk = 36
    versionCode = 1
    versionName = "0.1"

    // Developer Mode: both are "0". Real credentials come from Wearables Developer Center.
    manifestPlaceholders["mwdat_application_id"] =
        localProperties.getProperty("mwdat_application_id", "0")
    manifestPlaceholders["mwdat_client_token"] =
        localProperties.getProperty("mwdat_client_token", "0")
  }

  compileOptions {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
  }

  buildFeatures {
    compose = true
    buildConfig = true
  }
  packaging { resources { excludes += "/META-INF/{AL2.0,LGPL2.1}" } }
}

kotlin { compilerOptions { jvmTarget = JvmTarget.JVM_17 } }

dependencies {
  implementation(libs.androidx.activity.compose)
  implementation(platform(libs.androidx.compose.bom))
  implementation(libs.androidx.lifecycle.runtime.compose)
  implementation(libs.androidx.lifecycle.viewmodel.compose)
  implementation(libs.androidx.material3)
  implementation("com.google.android.gms:play-services-code-scanner:16.1.0") // QR scan, no camera permission
  implementation(libs.mwdat.core)
  implementation(libs.mwdat.display)
  implementation(libs.mwdat.mockdevice)
  implementation(libs.mwdat.speech)

}
