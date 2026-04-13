package com.example.comictranslator.ui.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.comictranslator.data.RetrofitClient
import com.example.comictranslator.data.TranslateRequest
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed class TranslationState {
    object Idle : TranslationState()
    object Loading : TranslationState()
    data class Processing(val message: String) : TranslationState()
    data class Success(val imageUrls: List<String>) : TranslationState()
    data class Error(val message: String) : TranslationState()
}

class MainViewModel : ViewModel() {
    private val _uiState = MutableStateFlow<TranslationState>(TranslationState.Idle)
    val uiState: StateFlow<TranslationState> = _uiState.asStateFlow()
    
    // Hardcoded IP for emulator -> host
    val baseUrl = "http://10.0.2.2:8000"

    fun startTranslation(url: String) {
        viewModelScope.launch {
            _uiState.value = TranslationState.Loading
            try {
                val response = RetrofitClient.apiService.startTranslation(TranslateRequest(url))
                val jobId = response.job_id
                pollJobStatus(jobId)
            } catch (e: Exception) {
                _uiState.value = TranslationState.Error("Failed to start translation: ${e.message}")
            }
        }
    }

    private suspend fun pollJobStatus(jobId: String) {
        var isCompleted = false
        while (!isCompleted) {
            delay(3000) // Poll every 3 seconds
            try {
                val statusResponse = RetrofitClient.apiService.getJobStatus(jobId)
                when (statusResponse.status) {
                    "completed" -> {
                        isCompleted = true
                        val fullUrls = statusResponse.result_images?.map { "$baseUrl$it" } ?: emptyList()
                        _uiState.value = TranslationState.Success(fullUrls)
                    }
                    "error", "failed" -> {
                        isCompleted = true
                        _uiState.value = TranslationState.Error(statusResponse.error ?: "Unknown error")
                    }
                    else -> {
                        _uiState.value = TranslationState.Processing("Status: ${statusResponse.status}")
                    }
                }
            } catch (e: Exception) {
                isCompleted = true
                _uiState.value = TranslationState.Error("Polling error: ${e.message}")
            }
        }
    }
    
    fun resetState() {
        _uiState.value = TranslationState.Idle
    }
}
