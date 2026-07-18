const { app, dialog } = require('electron')
const { spawn } = require('child_process')
const fs = require('fs')
const path = require('path')

const MODEL_REPOSITORY = 'csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17'
const MODEL_BASE_URL = `https://huggingface.co/${MODEL_REPOSITORY}/resolve/main`
const MIN_MODEL_SIZE = 220 * 1024 * 1024

async function downloadVoiceRecognitionModel() {
  const modelDirectory = path.join(app.getPath('userData'), 'models', 'manual-sensevoice')
  const model = path.join(modelDirectory, 'model.int8.onnx')
  const tokens = path.join(modelDirectory, 'tokens.txt')
  await fs.promises.mkdir(modelDirectory, { recursive: true })

  const existing = await fs.promises.stat(model).catch(() => null)
  if (existing?.size >= MIN_MODEL_SIZE && fs.existsSync(tokens)) return { downloaded: true, cached: true }

  await downloadFile(`${MODEL_BASE_URL}/model.int8.onnx?download=true`, model, MIN_MODEL_SIZE)
  await downloadFile(`${MODEL_BASE_URL}/tokens.txt?download=true`, tokens, 200 * 1024)
  return { downloaded: true, cached: false }
}

async function downloadFile(url, destination, minimumSize) {
  const partial = `${destination}.download`
  await runCurl([
    '-L',
    '--fail',
    '--retry', '5',
    '--retry-delay', '3',
    '--output', partial,
    url
  ])
  const downloaded = await fs.promises.stat(partial)
  if (downloaded.size < minimumSize) throw new Error('语音识别模型文件下载不完整')
  if (fs.existsSync(destination)) await fs.promises.copyFile(partial, destination)
  else await fs.promises.rename(partial, destination)
}

async function selectAndImportVoiceRecognitionModel(parentWindow) {
  const result = await dialog.showOpenDialog(parentWindow, {
    title: '选择 SenseVoice 模型目录',
    buttonLabel: '导入模型',
    properties: ['openDirectory', 'dontAddToRecent']
  })
  if (result.canceled || !result.filePaths[0]) return { canceled: true }

  const source = resolveModelRoot(path.resolve(result.filePaths[0]))
  if (!source) {
    return {
      canceled: false,
      imported: false,
      error: '目录中缺少 model.int8.onnx 或 tokens.txt。'
    }
  }

  const destination = path.join(app.getPath('userData'), 'models', 'manual-sensevoice')
  await fs.promises.mkdir(destination, { recursive: true })
  await fs.promises.cp(source, destination, {
    recursive: true,
    force: true,
    errorOnExist: false
  })
  return { canceled: false, imported: true }
}

function resolveModelRoot(selected) {
  const direct = hasModelFiles(selected) ? selected : null
  if (direct) return direct
  const children = fs.readdirSync(selected, { withFileTypes: true })
  for (const child of children) {
    if (!child.isDirectory()) continue
    const candidate = path.join(selected, child.name)
    if (hasModelFiles(candidate)) return candidate
  }
  return null
}

function hasModelFiles(directory) {
  return fs.existsSync(path.join(directory, 'model.int8.onnx')) && fs.existsSync(path.join(directory, 'tokens.txt'))
}

function runCurl(argumentsList) {
  return new Promise((resolve, reject) => {
    const process = spawn('curl.exe', argumentsList, {
      windowsHide: true,
      stdio: 'ignore'
    })
    process.once('error', reject)
    process.once('exit', code => {
      if (code === 0) resolve()
      else reject(new Error(`语音识别模型下载失败（curl ${code}）`))
    })
  })
}

module.exports = {
  downloadVoiceRecognitionModel,
  selectAndImportVoiceRecognitionModel
}
