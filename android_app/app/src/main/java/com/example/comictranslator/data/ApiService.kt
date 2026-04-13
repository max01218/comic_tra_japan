package com.example.comictranslator.data

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

// Response Models
data class TranslateRequest(val url: String)
data class TranslateResponse(val status: String, val job_id: String, val message: String)
data class JobStatusResponse(val status: String, val error: String? = null, val result_images: List<String>? = null)

// API Interface
interface TranslationApiService {
    @POST("translate")
    suspend fun startTranslation(@Body request: TranslateRequest): TranslateResponse

    @GET("status/{job_id}")
    suspend fun getJobStatus(@Path("job_id") jobId: String): JobStatusResponse
}

// Retrofit Client
object RetrofitClient {
    // Note: For Android Emulator to access localhost of host machine, use 10.0.2.2
    private const val BASE_URL = "http://10.0.2.2:8000/"

    val apiService: TranslationApiService by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(TranslationApiService::class.java)
    }
}
