const { app, dialog } = require('electron')
const { spawn } = require('child_process')
const fs = require('fs')
const path = require('path')

const MAX_FILE_SIZE = 5 * 1024 * 1024
const MAX_FILE_COUNT = 20
const SUPPORTED_EXTENSIONS = new Set(['.txt', '.md', '.json'])
const MODEL_ARCHIVE_URL = 'https://storage.googleapis.com/qdrant-fastembed/fast-bge-small-zh-v1.5.tar.gz'

async function selectKnowledgeFiles(parentWindow) {
  const result = await dialog.showOpenDialog(parentWindow, {
    title: '导入本地资料',
    buttonLabel: '加入知识库',
    properties: ['openFile', 'multiSelections', 'dontAddToRecent'],
    filters: [{ name: '文本资料', extensions: ['txt', 'md', 'json'] }]
  })
  if (result.canceled) return { canceled: true, files: [] }
  if (result.filePaths.length > MAX_FILE_COUNT) {
    return { canceled: false, error: `一次最多导入 ${MAX_FILE_COUNT} 个文件`, files: [] }
  }

  const files = []
  for (const filePath of result.filePaths) {
    const extension = path.extname(filePath).toLowerCase()
    if (!SUPPORTED_EXTENSIONS.has(extension)) continue
    const stats = await fs.promises.stat(filePath)
    if (stats.size > MAX_FILE_SIZE) {
      return { canceled: false, error: `${path.basename(filePath)} 超过 5 MB`, files: [] }
    }
    const content = (await fs.promises.readFile(filePath, 'utf8')).replace(/^\uFEFF/, '')
    files.push({
      title: path.basename(filePath),
      sourceType: extension.slice(1),
      content
    })
  }
  return { canceled: false, files }
}

async function selectAndImportEmbeddingModel(parentWindow) {
  const result = await dialog.showOpenDialog(parentWindow, {
    title: '选择 bge-small-zh-v1.5 模型目录',
    buttonLabel: '导入模型',
    properties: ['openDirectory', 'dontAddToRecent']
  })
  if (result.canceled || !result.filePaths[0]) return { canceled: true }

  const selected = path.resolve(result.filePaths[0])
  const source = resolveModelRoot(selected)
  const modelFile = findModelFile(source)
  if (!source || !modelFile || !fs.existsSync(path.join(source, 'tokenizer.json'))) {
    return {
      canceled: false,
      imported: false,
      error: '目录中缺少 tokenizer.json 或 ONNX 模型文件。'
    }
  }

  const destination = path.join(app.getPath('userData'), 'models', 'manual-bge-small-zh-v1.5')
  await fs.promises.mkdir(destination, { recursive: true })
  await fs.promises.cp(source, destination, {
    recursive: true,
    force: true,
    errorOnExist: false
  })
  const optimizedModel = path.join(destination, 'model_optimized.onnx')
  if (!fs.existsSync(optimizedModel)) {
    await fs.promises.copyFile(modelFile, optimizedModel)
  }

  return { canceled: false, imported: true }
}

async function downloadEmbeddingModel() {
  const modelDirectory = path.join(app.getPath('userData'), 'models')
  const archive = path.join(modelDirectory, 'fast-bge-small-zh-v1.5.tar.gz')
  const partial = `${archive}.part`
  await fs.promises.mkdir(modelDirectory, { recursive: true })

  const existing = await fs.promises.stat(archive).catch(() => null)
  if (!existing || existing.size < 10 * 1024 * 1024) {
    await runCurl([
      '-L',
      '--fail',
      '--retry', '5',
      '--retry-delay', '3',
      '--continue-at', '-',
      '--output', partial,
      MODEL_ARCHIVE_URL
    ])
    const downloaded = await fs.promises.stat(partial)
    if (downloaded.size < 10 * 1024 * 1024) throw new Error('模型归档下载不完整')
    if (existing) await fs.promises.copyFile(partial, archive)
    else await fs.promises.rename(partial, archive)
  }
  return { downloaded: true }
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
      else reject(new Error(`模型下载失败（curl ${code}）`))
    })
  })
}

function resolveModelRoot(selected) {
  const candidates = [selected, path.dirname(selected)]
  return candidates.find(candidate => (
    fs.existsSync(path.join(candidate, 'tokenizer.json')) && findModelFile(candidate)
  )) || null
}

function findModelFile(directory) {
  if (!directory) return null
  const candidates = [
    path.join(directory, 'model_optimized.onnx'),
    path.join(directory, 'model.onnx'),
    path.join(directory, 'onnx', 'model_optimized.onnx'),
    path.join(directory, 'onnx', 'model.onnx')
  ]
  return candidates.find(candidate => fs.existsSync(candidate)) || null
}

module.exports = {
  downloadEmbeddingModel,
  selectAndImportEmbeddingModel,
  selectKnowledgeFiles
}
