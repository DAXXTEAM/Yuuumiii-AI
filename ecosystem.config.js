module.exports = {
  apps: [
    {
      name: 'daxx-assistant',
      script: 'main.py',
      interpreter: 'python3',
      cwd: '/root/daxx-assistant'
    },
    {
      name: 'yuuumiii-bot',
      script: 'telegram_bot.py',
      interpreter: 'python3',
      cwd: '/root/daxx-assistant',
      restart_delay: 5000
    }
  ]
}
