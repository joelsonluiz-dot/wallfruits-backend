# COMANDOS PARA CORRIGIR ERRO DO RENDER

## Cole estes comandos no terminal (um de cada vez):

```powershell
# 1. Sincronizar com GitHub
git pull origin main --rebase

# 2. Adicionar todos os arquivos
git add -A

# 3. Fazer commit
git commit -m "Add complete project files"

# 4. Enviar para GitHub
git push origin main
```

## Depois que terminar o push:

1. No Render, clique em `Manual Deploy` -> `Deploy latest commit`
2. Aguarde o build (3-5 minutos)
3. Quando ficar `Live`, teste:
   - `https://wallfruits-api.onrender.com/health`
   - `https://wallfruits-api.onrender.com/docs`

## Se aparecer erro de porta ou SSL:

Verifique se as variáveis de ambiente incluem:
- `PORT` (Render adiciona automaticamente, não precisa criar)

## PRONTO!

Quando `/health` abrir no navegador, sua API está no ar para os usuários testarem! 🎉
