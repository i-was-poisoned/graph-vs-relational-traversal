# Entendiendo los Comandos de Git

Esta guía se construye desde los primeros principios: qué es Git en
realidad, cómo llega un commit desde tu portátil hasta GitHub, y qué hace
realmente cada comando que has usado hasta ahora (`add`, `commit`, `push`,
`pull`, `remote`, y más) por debajo — incluyendo el problema real de
credenciales que tuviste hoy y cómo se resolvió.

## 1. Qué es Git en realidad

Git es un **sistema de control de versiones**: toma instantáneas (snapshots)
de los archivos de tu proyecto a lo largo del tiempo, para que puedas ver el
historial, deshacer errores y — algo crucial para este proyecto — sincronizar
esas instantáneas entre tu portátil y un servidor remoto (GitHub). Git en sí
se ejecuta completamente en tu máquina; GitHub es solo un lugar donde
*también* puedes guardar una copia de tu historial de Git, para poder
respaldarlo, compartirlo o abrirlo desde otro ordenador.

## 2. El modelo de tres etapas: directorio de trabajo, área de preparación, repositorio

Este es el modelo mental más importante para entender cada uno de los
comandos siguientes. Un archivo de tu proyecto puede estar en uno de tres
"lugares" en lo que a Git respecta:

```
Directorio de Trabajo  --git add-->  Área de Preparación  --git commit-->  Repositorio (historial local)
(tus archivos reales                  (archivos marcados                   (instantáneas permanentes,
 en disco, tal como                    listos para el                       cada una identificada
 los editas)                           próximo commit)                      por un hash de commit)
```

- **Directorio de trabajo** — los archivos reales en tu disco, exactamente
  como los ves en VS Code ahora mismo. Editar un archivo solo cambia esta
  etapa.
- **Área de preparación** (también llamada "el índice" o *the index*) — un
  área de espera para los cambios que has decidido que *deben* incluirse en
  el próximo commit. Vas construyendo el área de preparación con `git add`.
- **Repositorio** — el historial permanente y nombrado de instantáneas
  ("commits"). `git commit` toma todo lo que esté actualmente preparado
  (staged) y lo sella en una nueva instantánea permanente dentro de este
  historial.

¿Por qué este paso extra de preparación, en lugar de simplemente confirmar
(commit) todo directamente? Te permite confirmar solo *algunos* de tus
cambios a la vez — por ejemplo, editaste tres archivos pero solo dos de ellos
están relacionados con lo que quieres que represente este commit. `git add`
elige qué se incluye; `git commit` sella esa elección.

## 3. `git status` — ¿cómo están las cosas?

Antes de hacer cualquier otra cosa, `git status` te dice: qué archivos están
preparados (staged), cuáles están modificados pero no preparados, y cuáles no
están rastreados (untracked, archivos nuevos que Git todavía no conoce). Es
de solo lectura — no cambia nada, así que siempre es seguro ejecutarlo y vale
la pena hacerlo a menudo, especialmente antes de `add`/`commit`/`push`.

## 4. `git add` — mover cambios al área de preparación

```bash
git add .
```

`git add <ruta>` prepara un archivo o carpeta específicos. `git add .`
prepara *todo* lo que haya cambiado o sea nuevo en el directorio actual y por
debajo — que es lo que ejecutaste, y está bien para un proyecto personal
pequeño donde revisas todo tú mismo. En proyectos más grandes o compartidos,
preparar archivos específicos por nombre es más seguro, ya que `.` puede
incluir accidentalmente archivos que no querías confirmar.

Este paso es puramente local — todavía no sale nada de tu máquina.

## 5. `git commit` — sellar una instantánea

```bash
git commit -m "Exploration stage set up"
```

Toma todo lo que está actualmente en el área de preparación y lo registra
permanentemente como una nueva instantánea en el historial de tu repositorio
local, etiquetada con el mensaje indicado después de `-m`. Cada commit
obtiene un identificador único (un "hash") y recuerda exactamente qué cambió
y cuándo. Esto sigue siendo completamente local — un commit existe solo en tu
portátil hasta que lo envías (push) a algún lugar.

Un buen mensaje de commit dice *por qué*/*qué* cambió de un vistazo — por eso
antes optamos por algo como `"Exploration stage set up"`, en lugar de algo
vago como `"updates"`.

## 6. `git remote` — ¿qué significa "en otro lugar"?

Un **remoto** (remote) es simplemente un apodo guardado para otra copia del
repositorio en algún otro lugar — casi siempre una URL que apunta a un
repositorio de GitHub (o similar). El apodo predeterminado que usa Git es
`origin`, pero eso es solo una convención, no un requisito.

```bash
git remote -v
```

Muestra todos los remotos que este repositorio local conoce, con sus URLs,
tanto para la dirección `fetch` (descarga) como `push` (subida) —
normalmente idénticas. Es un comando de solo lectura, puramente informativo.
Ejecutarlo fue lo que reveló hoy que `origin` apuntaba a
`https://github.com/Winteroc18pedro/graph-vs-relational-traversal.git`.

### `git remote set-url` — cambiar a dónde apunta un remoto

```bash
git remote set-url origin https://i-was-poisoned@github.com/i-was-poisoned/graph-vs-relational-traversal.git
```

Cambia la URL guardada bajo un apodo de remoto existente (`origin`), sin
tocar en absoluto tu historial de commits — solo afecta a con quién hablan
los futuros comandos `push`/`pull`. Esto se guarda en el propio archivo local
`.git/config` de este repositorio, así que solo afecta a *este* repositorio,
nunca a ningún otro repositorio en tu máquina.

**Por qué necesitamos esto hoy:** tu máquina Windows tenía guardado en el
Administrador de Credenciales (Credential Manager) un inicio de sesión de
GitHub para tu cuenta de trabajo de Celfocus (`NB30006_celfocus`), y
`git push` estaba usando silenciosamente ese inicio de sesión guardado porque
la URL del remoto (`https://github.com/...`) no especificaba *con qué* cuenta
autenticarse. GitHub rechazó correctamente el push con un error 403, porque
esa cuenta de trabajo no tiene permisos sobre tu repositorio personal.

Incrustar tu nombre de usuario real directamente en la URL
(`https://i-was-poisoned@github.com/...`) le indica al gestor de credenciales
de Git que busque (y guarde) las credenciales bajo una clave *separada*,
específica para ese nombre de usuario, en lugar de reutilizar lo que se
guardó por última vez para `github.com` a secas. Eso fue lo que permitió que
el siguiente `git push` solicitara un nuevo inicio de sesión para la cuenta
correcta, sin alterar la credencial de trabajo guardada que usan tus
repositorios de Celfocus.

## 7. `git push` — enviar commits locales a un remoto

```bash
git push
```

Sube cualquier commit que exista en tu repositorio local pero que todavía no
esté en la copia del remoto, para la rama actual. Este es el paso que
realmente requiere autenticación, ya que estás escribiendo en el servidor de
otra persona (GitHub) — de ahí que sea aquí donde apareció el error de
permisos.

### `git push -u origin main` (también conocido como `--set-upstream`)

```bash
git push -u origin main
```

`-u` (abreviatura de `--set-upstream`) hace una cosa extra además de un push
normal: le indica a tu rama local `main` que "siga" (track) a la rama `main`
del `origin`, recordando esa asociación. Después de ejecutar esto **una
vez**, un `git push` o `git pull` simples (sin argumentos adicionales) saben
automáticamente con qué remoto y rama hablar, ya que ese vínculo queda
recordado. Sin esto, Git te pediría especificar el remoto y la rama por
nombre cada vez.

Necesitas `-u` la *primera* vez que envías (push) una rama local dada a una
rama remota dada; después de eso, un `git push` simple es suficiente.

## 8. `git pull` — traer los commits del remoto hacia ti

```bash
git pull
```

La dirección inversa de `git push`: descarga cualquier commit que exista en
el remoto pero que todavía no esté en tu repositorio local, y lo fusiona
(merge) en tu rama actual. Todavía no se ha usado en este proyecto (ya que
hasta ahora eres el único colaborador y no existe nada en el remoto que no
esté ya en local), pero esto es lo que ejecutarías antes de empezar un nuevo
trabajo si estuvieras colaborando con otra persona, o trabajando desde una
segunda máquina, para asegurarte de estar construyendo sobre la versión más
reciente.

## 9. `git clone` — obtener un repositorio remoto por primera vez

```bash
git clone https://github.com/i-was-poisoned/graph-vs-relational-traversal.git
```

Así es como se creó originalmente la copia local en `C:\dev\Research` (como
se explica en la sección "Flujo de Trabajo del Repositorio Hasta Ahora" de
[project-notes.md](project-notes.md)): descarga todo el historial de un
repositorio remoto y lo configura como un nuevo repositorio local,
configurando automáticamente `origin` para que apunte de vuelta a la URL
desde la que clonaste. Solo ejecutas esto una vez, al principio de todo —
después de eso, `pull`/`push` se encargan de mantener ambos sincronizados.

## 10. Otros comandos que vale la pena conocer

- **`git log`** — muestra el historial de commits (mensaje, autor, fecha,
  hash) de la rama actual. Añade `--oneline` para una vista compacta de una
  línea por commit.
- **`git diff`** — muestra los cambios exactos, línea por línea, que están
  preparados o sin preparar pero todavía no confirmados (committed). Útil
  para revisar exactamente qué estás a punto de `add`/`commit` antes de
  hacerlo.
- **`git branch`** — lista las ramas locales (este proyecto solo ha usado
  `main` hasta ahora); también se usa para crear ramas nuevas
  (`git branch <nombre>`) cuando quieres trabajar en algo sin afectar
  directamente a `main`.

## 11. Referencia Rápida

| Comando | Qué hace | ¿Toca el remoto? |
|---|---|---|
| `git status` | Muestra qué ha cambiado/qué está preparado | No |
| `git add .` | Prepara todos los cambios | No |
| `git commit -m "..."` | Guarda una instantánea localmente | No |
| `git remote -v` | Lista los remotos configurados | No (solo lectura) |
| `git remote set-url origin <url>` | Cambia a dónde apunta un remoto | No |
| `git push` | Sube los commits locales | Sí |
| `git push -u origin main` | Sube + vincula las ramas local/remota (solo la primera vez) | Sí |
| `git pull` | Descarga + fusiona los commits del remoto | Sí |
| `git clone <url>` | Obtiene una copia completa de un repositorio remoto (una sola vez) | Sí |
