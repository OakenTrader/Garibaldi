
<script>
import extractZip from '@/scripts/extract_zip.py?raw'
import installDeps from '@/scripts/install_deps.py?raw'
import runExtractor from '@/scripts/runExtractor.py?raw'
export default {
  data() {
    return { pyodide: null }
  },

  async created() {
    console.log('load Pyodide...')
    // Dynamisch das lokale pyodide.js aus /public/pyodide/ laden
    await new Promise((resolve, reject) => {
      const s = document.createElement('script')
      s.src = '/pyodide/pyodide.js'
      s.onload = resolve
      s.onerror = reject
      document.head.appendChild(s)
    })

    // loadPyodide ist jetzt global verfügbar
    this.pyodide = await globalThis.loadPyodide({
      indexURL: '/pyodide/',
    })
    console.log('Pyodide loaded')
  },

  methods: {
    // =========================
    // Main entry point
    // =========================
    async runPythonProject() {
      try {
        await this.downloadZip('/python.zip')
        await this.extractZip('python.zip', 'project')
        await this.installDependencies('project/requirements.txt')
        await this.runMainPy('project/')
      } catch (err) {
        console.error('Error running Python project:', err)
      }
    },

    // =========================
    // Download ZIP from server
    // =========================
    async downloadZip(url) {
      console.log('Downloading ZIP:', url)
      const response = await fetch(url)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const buffer = await response.arrayBuffer()
      const uint8Array = new Uint8Array(buffer)
      this.pyodide.FS.writeFile('python.zip', uint8Array)
      console.log('ZIP saved in Pyodide FS')
    },

    // =========================
    // Extract ZIP in Pyodide FS
    // =========================
async extractZip(zipPath, extractTo) {
  console.log('Extracting ZIP...')
  await this.pyodide.runPythonAsync(
    extractZip
      .replaceAll('${zipPath}', zipPath)
      .replaceAll('${extractTo}', extractTo)
  )
},

    // =========================
    // Install dependencies from requirements.txt
    // =========================
    async installDependencies(reqPath) {
      console.log('Installing dependencies...')
      await this.pyodide.loadPackage('micropip')
      await this.pyodide.runPythonAsync(`
import os
print("Root:", os.listdir("/"))
print("Project:", os.listdir("project"))
print("Project/python:", os.listdir("project"))
`)
      await this.pyodide.runPythonAsync(
                installDeps
      .replaceAll('${reqPath}', reqPath)
  )
    },

    // =========================
    // Run main.py
    // =========================
    async runMainPy(projectPath) {
      console.log('Running main.py...')

      const result = await this.pyodide.runPythonAsync(
                runExtractor
      .replaceAll('${projectPath}', projectPath)
  )
      console.log('Python output:', result)
    },
  },
}
</script>

<template>
  <button @click="runPythonProject">Run Python Project</button>
</template>
