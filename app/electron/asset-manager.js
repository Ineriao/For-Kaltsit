const { app, dialog } = require('electron')
const fs = require('fs')
const path = require('path')

const REQUIRED_ASSET_PATHS = [
  path.join('illustration', '立绘_凯尔希·思衡托_1.png'),
  path.join('spine', 'SpineModel', 'char_1052_kalts2', 'Building', 'build_char_1052_kalts2', 'build_char_1052_kalts2.atlas'),
  path.join('spine', 'SpineModel', 'char_1052_kalts2', 'Building', 'build_char_1052_kalts2', 'build_char_1052_kalts2.skel')
]

function getImportedAssetsDirectory() {
  return path.join(app.getPath('userData'), 'assets')
}

function validateAssetsDirectory(directory) {
  if (!directory) return { valid: false, missing: [...REQUIRED_ASSET_PATHS] }
  const missing = REQUIRED_ASSET_PATHS.filter(relativePath => (
    !fs.existsSync(path.join(directory, relativePath))
  ))
  return { valid: missing.length === 0, missing }
}

function resolveSelectedAssetsRoot(selectedDirectory) {
  const direct = path.resolve(selectedDirectory)
  if (validateAssetsDirectory(direct).valid) return direct

  const nested = path.join(direct, 'assets')
  if (validateAssetsDirectory(nested).valid) return nested
  return direct
}

async function selectAndImportAssets(parentWindow) {
  const result = await dialog.showOpenDialog(parentWindow, {
    title: '选择明日方舟资源目录',
    buttonLabel: '导入资源',
    properties: ['openDirectory', 'dontAddToRecent']
  })
  if (result.canceled || !result.filePaths[0]) return { canceled: true }

  const source = resolveSelectedAssetsRoot(result.filePaths[0])
  const validation = validateAssetsDirectory(source)
  if (!validation.valid) {
    return {
      canceled: false,
      imported: false,
      error: '所选目录缺少立绘或 Spine 模型文件。',
      missing: validation.missing
    }
  }

  const destination = getImportedAssetsDirectory()
  if (path.resolve(source) !== path.resolve(destination)) {
    await fs.promises.mkdir(destination, { recursive: true })
    await fs.promises.cp(source, destination, {
      recursive: true,
      force: true,
      errorOnExist: false
    })
  }

  return {
    canceled: false,
    imported: true,
    directory: destination,
    validation: validateAssetsDirectory(destination)
  }
}

module.exports = {
  getImportedAssetsDirectory,
  selectAndImportAssets,
  validateAssetsDirectory
}
