<script>
import { loadPyodide } from 'pyodide'

export default {
  async created() {
    this.pyodide = await loadPyodide()
  },
  methods: {
    async runPython() {
      // kein loadPackage - stattdessen einfach pyodide benutzen
      const code = `
    print("Hello from Pyodide!")
    # Add your Python code here
  `
      const result = await this.pyodide.runPythonAsync(code)
      console.log(result)
    },
  },
}
</script>

<template>
  <button @click="runPython">Run Python</button>
</template>
