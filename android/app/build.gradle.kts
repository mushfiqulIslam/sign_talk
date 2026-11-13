import java.util.Properties
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
  alias(libs.plugins.android.application)
  alias(libs.plugins.jetbrains.kotlin.android)
  alias(libs.plugins.compose.compiler)
}

val localProperties =
    Properties().apply {
      val file = rootDir.resolve("local.properties")
      if (file.exists()) file.inputStream().use { load(it) }
    }

android {
  namespace = "com.signtalk.app"
  compileSdk = 36

  defaultConfig {
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

  buildFeatures { compose = true }
  packaging { resources { excludes += "/META-INF/{AL2.0,LGPL2.1}" } }
}

kotlin { compilerOptions { jvmTarget = JvmTarget.JVM_17 } }

dependencies {
  implementation(libs.androidx.activity.compose)
  implementation(platform(libs.androidx.compose.bom))
  implementation(libs.androidx.lifecycle.runtime.compose)
  implementation(libs.androidx.lifecycle.viewmodel.compose)
  implementation(libs.androidx.material3)
  implementation(libs.mwdat.core)
  implementation(libs.mwdat.display)
  implementation(libs.mwdat.mockdevice)
}
