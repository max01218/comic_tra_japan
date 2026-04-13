package com.example.comictranslator.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Translate
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import com.example.comictranslator.ui.viewmodels.MainViewModel
import com.example.comictranslator.ui.viewmodels.TranslationState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(viewModel: MainViewModel = viewModel()) {
    var urlText by remember { mutableStateOf(TextFieldValue("")) }
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("漫畫翻譯器") },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    titleContentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                )
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .padding(innerPadding)
                .fillMaxSize()
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            InputSection(urlText, onUrlChange = { urlText = it }) {
                viewModel.startTranslation(urlText.text)
            }
            
            Spacer(modifier = Modifier.height(24.dp))
            HorizontalDivider()
            Spacer(modifier = Modifier.height(16.dp))
            
            ResultSection(uiState)
        }
    }
}

@Composable
fun InputSection(urlText: TextFieldValue, onUrlChange: (TextFieldValue) -> Unit, onTranslateSubmit: () -> Unit) {
    Icon(
        imageVector = Icons.Default.Translate,
        contentDescription = "Translate Icon",
        modifier = Modifier.size(56.dp),
        tint = MaterialTheme.colorScheme.primary
    )
    
    Spacer(modifier = Modifier.height(16.dp))
    
    OutlinedTextField(
        value = urlText,
        onValueChange = onUrlChange,
        label = { Text("請輸入漫畫網址") },
        placeholder = { Text("https://example.com/comic/page1") },
        modifier = Modifier.fillMaxWidth(),
        singleLine = true
    )
    
    Spacer(modifier = Modifier.height(16.dp))
    
    Button(
        onClick = onTranslateSubmit,
        modifier = Modifier
            .fillMaxWidth()
            .height(56.dp),
        enabled = urlText.text.isNotBlank()
    ) {
        Text("開始翻譯", style = MaterialTheme.typography.titleMedium)
    }
}

@Composable
fun ResultSection(uiState: TranslationState) {
    when (uiState) {
        is TranslationState.Idle -> {
            Text("等待輸入網址...", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        is TranslationState.Loading, is TranslationState.Processing -> {
            val msg = if (uiState is TranslationState.Processing) uiState.message else "連線中..."
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                CircularProgressIndicator()
                Spacer(modifier = Modifier.height(16.dp))
                Text(msg)
            }
        }
        is TranslationState.Error -> {
            Text("發生錯誤：\n${uiState.message}", color = MaterialTheme.colorScheme.error)
        }
        is TranslationState.Success -> {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(uiState.imageUrls) { imageUrl ->
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
                    ) {
                        AsyncImage(
                            model = imageUrl,
                            contentDescription = "Translated Comic Page",
                            modifier = Modifier.fillMaxWidth(),
                            contentScale = ContentScale.FillWidth
                        )
                    }
                }
            }
        }
    }
}
