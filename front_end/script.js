const API = 'http://127.0.0.1:5000/api'

const terminal = document.getElementById('terminal')
const runBtn = document.getElementById('runBtn')
const flowSelect = document.getElementById('flowSelect')
const historyTable = document.getElementById('historyTable')

async function loadFlows() {

  const response = await fetch(`${API}/flows`)
  const flows = await response.json()

  flowSelect.innerHTML = ''

  flows.forEach(flow => {

    const option = document.createElement('option')

    option.value = flow
    option.textContent = flow

    flowSelect.appendChild(option)

  })

}

async function runFlow() {

  await fetch(`${API}/run`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      flow: flowSelect.value
    })
  })

}

async function loadLogs() {

  const response = await fetch(`${API}/logs`)
  const logs = await response.json()

  terminal.innerHTML = ''

  logs.forEach(log => {

    const p = document.createElement('p')

    p.textContent = log

    if (log.includes('[ERROR]')) {
      p.classList.add('error-log')
    }

    terminal.appendChild(p)

  })

  terminal.scrollTop = terminal.scrollHeight

}

async function loadStatus() {

  const response = await fetch(`${API}/status`)
  const status = await response.json()

  document.getElementById('passed').textContent = status.passed
  document.getElementById('failed').textContent = status.failed
  document.getElementById('executing').textContent = status.executing
  document.getElementById('lastExecution').textContent = status.last_execution

}

async function loadHistory() {

  const response = await fetch(`${API}/history`)
  const history = await response.json()

  historyTable.innerHTML = ''

  history.forEach(item => {

    const tr = document.createElement('tr')

    tr.innerHTML = `
      <td>${item.flow}</td>
      <td>${item.date}</td>
      <td>${item.duration}</td>
      <td>
        <span class="badge ${item.result === 'PASSOU' ? 'pass' : 'fail'}">
          ${item.result}
        </span>
      </td>
    `

    historyTable.appendChild(tr)

  })

}

runBtn.addEventListener('click', runFlow)

loadFlows()

setInterval(() => {

  loadLogs()
  loadStatus()
  loadHistory()

}, 1000)