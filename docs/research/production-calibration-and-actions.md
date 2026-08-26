# Production calibration data and GitHub Actions in the Wardrowbe fork

Дата проверки: 2026-08-27  
Репозиторий: `theEvgene/wardrowbe` (fork `Anyesh/wardrowbe`)  
Ограничение исследования: только первичные источники — GitHub Docs/Status/REST API, официальные страницы и лицензии датасетов, официальные страницы конкретных изображений.

> Это инженерная оценка лицензий, а не юридическое заключение. Для публичного коммерчески совместимого репозитория нужно сохранять доказательства происхождения каждого файла и отдельно учитывать права изображённых людей, бренды и товарные знаки.

## Краткий вывод

1. **Текущая конфигурация Wardrowbe должна запускать CI на обычный push в `main`.** GitHub REST API показывает, что репозиторий является fork с default branch `main`, Actions включены, разрешены все actions, workflow `CI` активен, а `.github/workflows/ci.yml` содержит `push.branches: [main, master]` без path-фильтров. GitHub зарегистрировал публичное `PushEvent` в `refs/heads/main`, но API не показывает ни одного run с `event=push`; два run с `event=workflow_dispatch` успешно завершились.
2. Документированные причины — выключенные Actions в fork, disabled workflow, несовпавшие branch/path-фильтры, skip-аннотация и push с репозиторным `GITHUB_TOKEN` — объясняют такой симптом в общем случае, но **по доступным данным не объясняют последний push Wardrowbe**. Наиболее полезная следующая диагностика без PR — контролируемый пустой commit, отправленный напрямую пользовательским PAT/SSH после восстановления GitHub Actions. Если run снова не появится, следует переактивировать workflow и передать GitHub Support идентификатор push-события, SHA и workflow ID.
3. Для небольшой публичной выборки реальных снимков лучший готовый источник — **Open Images V6/V7**: изображения перечислены как CC BY 2.0, аннотации и маски Google — CC BY 4.0; среди официальных segmentation classes есть `Person`, `Clothing`, `Shirt`, `Trousers`, `Jeans`, `Shorts`, `Skirt`, `Miniskirt`, `Dress` и `Suit`. Лицензию исходной Flickr-страницы всё равно нужно проверять для каждого выбранного изображения, потому что Open Images прямо отказывается гарантировать её корректность.
4. Самый низкорисковый источник — **собственные реально снятые фотографии** с письменным согласием изображённого человека и отдельной лицензией CC0 или CC BY 4.0. Дополнительные единичные CC0-фотографии можно брать с Wikimedia Commons и размечать вручную; ниже приведены три конкретных кандидата для upper/lower/full-garment сценариев.
5. Не следует переносить в публичный репозиторий изображения из DeepFashion, Supervisely Person, Fashionpedia, Unsplash Dataset или Pexels без отдельного разрешения: их официальные условия содержат запрет на дальнейшее распространение, non-commercial ограничения, неоднородные права на изображения или прямые ограничения для ML-датасетов.

## 1. Почему push-triggered runs могут отсутствовать во fork

### Фактическое состояние Wardrowbe

Проверка выполнена через официальные REST endpoints GitHub и текущий workflow из default branch.

| Проверка | Фактический результат |
|---|---|
| Репозиторий | `fork: true`, parent `Anyesh/wardrowbe`, default branch `main` ([repository API](https://api.github.com/repos/theEvgene/wardrowbe)) |
| Actions policy | `enabled: true`, `allowed_actions: all`, `sha_pinning_required: false` (`GET /repos/{owner}/{repo}/actions/permissions`; [документация endpoint](https://docs.github.com/en/rest/actions/permissions#get-github-actions-permissions-for-a-repository)) |
| Workflow | `CI`, ID `342689330`, path `.github/workflows/ci.yml`, state `active` ([workflows API](https://api.github.com/repos/theEvgene/wardrowbe/actions/workflows)) |
| Trigger в default branch | `workflow_dispatch`, `push.branches: [main, master]`, `pull_request.branches: [main, master]`; path-фильтров нет |
| Push run history | `total_count: 0` для `event=push` ([runs API](https://api.github.com/repos/theEvgene/wardrowbe/actions/runs?event=push&per_page=20)) |
| Manual run history | два успешных `workflow_dispatch`: run `33007684822` на `830dbad` и run `33010527769` на `d5ff0f2` ([runs API](https://api.github.com/repos/theEvgene/wardrowbe/actions/runs?event=workflow_dispatch&per_page=20)) |
| Последний наблюдавшийся push | actor `theEvgene`, `refs/heads/main`, `830dbad` → `d5ff0f2`, публичный PushEvent ID `18992019854`, 2026-08-26 20:27:30 UTC ([repository events API](https://api.github.com/repos/theEvgene/wardrowbe/events?per_page=30)) |
| Commit messages | В последних commit messages нет `[skip ci]`, `[ci skip]`, `[no ci]`, `[skip actions]`, `[actions skip]` или `skip-checks` trailer |

Инцидент GitHub Actions 26 августа завершён в 18:01:30 UTC; в финальном обновлении GitHub сообщил, что входящие очереди восстановлены, новые jobs обрабатываются, а компонент Actions переведён в `operational` ([официальный incident API](https://www.githubstatus.com/api/v2/incidents.json)). При повторной проверке 27 августа общий Status API сообщает `All Systems Operational`, а компонент `Actions` — `operational` ([status API](https://www.githubstatus.com/api/v2/status.json), [components API](https://www.githubstatus.com/api/v2/components.json)). Последний push Wardrowbe произошёл примерно через 2 часа 26 минут после официального завершения инцидента, поэтому сам инцидент не является достаточным объяснением отсутствия этого run.

### Документированные причины и применимость

| Причина | Что говорит GitHub | Применимость к Wardrowbe |
|---|---|---|
| Workflows в fork не включены | Workflows в fork по умолчанию не запускаются; их нужно включить на вкладке Actions ([Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflows-in-forked-repositories)). | Исключено для текущего состояния: workflow `active`, Actions `enabled`, manual runs проходят. |
| Actions запрещены на уровне repository/organization/enterprise | Repository Actions settings могут полностью выключить Actions или ограничить разрешённые actions; более высокий policy может переопределять repository setting ([Managing GitHub Actions settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository)). | Исключено для персонального fork по API: `enabled: true`, `allowed_actions: all`; manual job использует внешние actions и проходит. |
| Workflow disabled | Disabled workflow не отвечает на triggers; его можно включить через UI, CLI или REST API ([Disabling and enabling a workflow](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)). | Исключено: state `active`, manual runs проходят. |
| Branch/tag/path filter не совпал | `push.branches`, `tags`, `paths` и ignore-варианты ограничивают trigger; если одновременно заданы branch и path filters, должны совпасть оба ([Triggering a workflow](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow#using-filters)). | Исключено для последнего push: ref `refs/heads/main`, `main` разрешён, path-фильтров нет. |
| Workflow file отсутствует/не тот в нужном ref | `on` задаёт автоматические events; `workflow_dispatch` доступен только если workflow file находится в default branch ([Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onworkflow_dispatch)). | Исключено: default branch `main`, manual dispatch этого файла работает, текущий файл содержит `push`. |
| Commit просит пропустить CI | Push/pull_request workflow пропускается при поддерживаемой skip-аннотации или `skip-checks` trailer ([Skipping workflow runs](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/skipping-workflow-runs)). | Исключено для проверенных commit messages. |
| Push создан репозиторным `GITHUB_TOKEN` | События, созданные `GITHUB_TOKEN`, обычно не создают новый workflow run; исключения — `workflow_dispatch`, `repository_dispatch` и отдельный approval-required PR case ([GITHUB_TOKEN](https://docs.github.com/en/actions/concepts/security/github_token#when-github_token-triggers-workflow-runs)). | Это точно объясняло бы комбинацию «push молчит, workflow_dispatch работает», но публичный PushEvent имеет actor `theEvgene`, а push был локальным. Нужно окончательно удостовериться, что git credential был пользовательским PAT/SSH, а не installation token. |
| Fork PR approval policy | Approval policies относятся к workflows, инициированным pull request из fork; PR events происходят в base repository, а не в fork ([Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull-request-events-for-forked-repositories)). | Неприменимо: используется прямой push в собственный fork, PR отсутствует. |

### Вывод для Wardrowbe

Доступные официальные данные не показывают текущую статическую настройку, которая законно подавляла бы этот push trigger. GitHub принял push и зарегистрировал `PushEvent`, но Actions не создал соответствующий run. Это оставляет три практических гипотезы:

1. push был аутентифицирован installation/repository `GITHUB_TOKEN` вопреки пользовательскому actor в публичном событии;
2. состояние auto-trigger в fork осталось неконсистентным после первоначального включения workflows;
3. GitHub потерял конкретное событие или сохраняется недокументированная проблема ingestion для этого repository после инцидента.

Пункты 2–3 являются выводами по исключению, а не подтверждённым GitHub RCA.

### Диагностика и исправление без PR

1. **Зафиксировать текущее состояние read-only:**

   ```powershell
   gh api repos/theEvgene/wardrowbe/actions/permissions
   gh api repos/theEvgene/wardrowbe/actions/workflows
   gh api 'repos/theEvgene/wardrowbe/actions/runs?event=push&branch=main&per_page=20'
   gh api 'repos/theEvgene/wardrowbe/actions/runs?event=workflow_dispatch&branch=main&per_page=20'
   ```

2. **Проверить credential происхождения push.** Не выполнять push из job с `${{ secrets.GITHUB_TOKEN }}`/`github.token`. Если push выполняет автоматизация, использовать GitHub App installation token или пользовательский fine-grained PAT с минимальными правами; GitHub прямо рекомендует App token/PAT, когда событие должно запустить следующий workflow ([Triggering a workflow](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow#triggering-a-workflow-from-a-workflow)). Для локальной проверки предпочтительны обычный пользовательский SSH credential или PAT.
3. **Сделать контролируемый push без изменения файлов и без PR:**

   ```powershell
   git commit --allow-empty -m "ci: diagnose push trigger"
   git push fork HEAD:main
   gh run list --repo theEvgene/wardrowbe --workflow CI --event push --branch main --limit 5
   ```

   Если run появился, предыдущий event был потерян/подавлен транзиентно; `workflow_dispatch` остаётся корректным ручным способом проверить конкретный SHA.
4. **Если run снова отсутствует, переактивировать только workflow** и повторить один empty commit:

   ```powershell
   gh workflow disable .github/workflows/ci.yml --repo theEvgene/wardrowbe
   gh workflow enable .github/workflows/ci.yml --repo theEvgene/wardrowbe
   ```

   Это не требует PR и не изменяет историю или файлы. Полное выключение/включение Actions repository-wide — более широкий следующий шаг и пока не обосновано, так как manual runs работают.
5. **Если второй контрольный push также не создаст run, обратиться в GitHub Support** с repository `theEvgene/wardrowbe`, workflow ID `342689330`, default branch `main`, отсутствующим run, SHA, UTC timestamp и PushEvent ID. Это уже platform/repository-state проблема, которую нельзя подтвердить или исправить YAML-изменением.

## 2. Реальные изображения для публичной calibration fixture set

### Рекомендованный порядок источников

1. Собственные снимки Wardrowbe с письменным согласием модели и явной лицензией.
2. Небольшой, пофайлово проверенный subset Open Images V6/V7 с готовыми instance masks.
3. Отдельные CC0/CC BY изображения Wikimedia Commons с ручной разметкой масок.

Не следует помещать сторонние изображения под общую лицензию исходного кода. Для `backend/tests/fixtures/...` нужен отдельный manifest/README с лицензией и происхождением каждого JPEG/PNG и каждой mask annotation.

### Вариант A — Open Images V6/V7: основной готовый источник

Официальная страница Open Images сообщает о 2.8 млн instance segmentation masks для 350 classes; train masks создавались интерактивным процессом с профессиональными human annotators ([V7 description](https://storage.googleapis.com/openimages/web/factsfigures_v7.html#object-segmentations)). Официальные файлы [`classes-segmentation.txt`](https://storage.googleapis.com/openimages/v5/classes-segmentation.txt) и [`class-descriptions-boxable.csv`](https://storage.googleapis.com/openimages/v5/class-descriptions-boxable.csv) вместе подтверждают наличие следующих релевантных mask classes:

| Сценарий Wardrowbe | Open Images segmentation classes |
|---|---|
| Верхняя одежда | `Shirt`, `Clothing`, при необходимости `Suit` |
| Нижняя одежда | `Trousers`, `Jeans`, `Shorts`, `Skirt`, `Miniskirt` |
| Full-garment/full-body | `Dress`, `Suit`, вместе с `Person` |
| Контроль semantic leakage | Соседние маски `Person` и нескольких garment classes в одном реальном кадре |

Лицензирование:

- изображения **перечислены** как [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/);
- annotations лицензированы Google LLC под [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/);
- Open Images предупреждает, что не гарантирует лицензионный статус каждого изображения, поэтому его следует проверить самостоятельно ([официальный раздел Licenses](https://storage.googleapis.com/openimages/web/factsfigures_v7.html#licenses));
- официальный image metadata содержит `ImageID`, original/landing URL, license URL, author profile, author и title, то есть данные, необходимые для attribution ([официальный download/data format](https://storage.googleapis.com/openimages/web/download.html#dataformats)).

Практическая выборка для Wardrowbe: 9–12 validation images — по 3–4 `Shirt`, lower-body (`Trousers`/`Jeans`/`Skirt`) и `Dress`/`Suit`; хотя бы один кадр в каждой группе должен иметь occlusion, несколько предметов одежды или сложный фон. Включать изображение можно только если исходная landing page доступна и по-прежнему подтверждает подходящую лицензию.

Для каждого файла сохранить:

- Open Images `ImageID`, split и mask filename/BoxID;
- author, title, original landing URL и author profile URL;
- ссылку `https://creativecommons.org/licenses/by/2.0/`;
- пометку о resize/crop/encoding changes;
- для маски: `Open Images annotations © Google LLC, CC BY 4.0` и ссылку на dataset page;
- дату проверки лицензии и SHA-256 локального файла.

### Вариант B — собственные реальные фотографии: минимальный правовой риск

Снять 6–9 фотографий: минимум по две upper, lower и dress/full-body, плюс 1–3 сложных случая semantic leakage (руки поверх футболки, куртка поверх рубашки, длинный верх рядом с брюками). Фотограф/правообладатель должен письменно выпустить файлы под [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) или [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), а изображённый человек — дать согласие на публичное распространение и ML evaluation/training use.

CC BY 4.0 разрешает копирование, изменение и коммерческое использование, но требует appropriate credit, ссылки на лицензию и указания изменений. Creative Commons отдельно предупреждает, что privacy, publicity и moral rights могут ограничивать использование даже при наличии copyright license ([официальный CC BY 4.0 deed](https://creativecommons.org/licenses/by/4.0/deed.en)). Поэтому согласие модели нужно хранить отдельно от репозитория, а в публичном manifest фиксировать только наличие release без персональных данных.

### Вариант C — три конкретных CC0-кандидата Wikimedia Commons

Эти файлы — реальные фотографии и допускают копирование/изменение/распространение без обязательной атрибуции по CC0; provenance всё равно рекомендуется сохранить. Готовых garment masks у них нет — Wardrowbe должен вручную создать и проверить masks.

| Сценарий | Кандидат | Лицензия и provenance | Почему полезен |
|---|---|---|---|
| Upper + occlusion/leakage | [Man with marinière t-shirt and backpack.jpg](https://commons.wikimedia.org/wiki/File:Man_with_marini%C3%A8re_t-shirt_and_backpack.jpg) | Own work, author `DimiTalen`, CC0 1.0 | Реальный человек, полосатая футболка и рюкзак; подходит для проверки, что рюкзак/руки/брюки не протекают в garment mask. |
| Lower | [Human feet and black trousers.jpg](https://commons.wikimedia.org/wiki/File:Human_feet_and_black_trousers.jpg) | Own work, author `Mn1203`, CC0 1.0 | Кадр нижней части тела без лица, чёрные брюки и стопы; низкий privacy risk и явная lower-body граница. |
| Full garment / dress | [Woman in a dress (Unsplash m1WzQ4jkWF8).jpg](https://commons.wikimedia.org/wiki/File:Woman_in_a_dress_%28Unsplash_m1WzQ4jkWF8%29.jpg) | Author `Inma Ibáñez`; опубликовано до 2017-06-05 под CC0 1.0, что зафиксировано на Commons file page | Современная реально снятая сцена с платьем; подходит для full-garment mask и сложного естественного фона. |

Wikimedia Commons требует проверять license на странице каждого файла и предупреждает о возможных non-copyright restrictions, особенно personality rights изображённых людей ([официальное руководство по reuse](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia/en)). Поэтому перед включением нужно визуально проверить отсутствие несовершеннолетних, чувствительного контекста, заметных брендов и легко идентифицируемого лица; при сомнении заменить файл собственным consented capture.

### Источники, которые не следует копировать в public repo без отдельного разрешения

| Источник | Официальное ограничение | Решение для Wardrowbe |
|---|---|---|
| DeepFashion | Только non-commercial research; запрещено further copy/publish/distribute portions of the dataset ([official DeepFashion agreement/page](https://mmlab.ie.cuhk.edu.hk/projects/DeepFashion.html)). | Не включать изображения или derived data в публичный repo. |
| Supervisely Person Dataset | Доступен academic/non-academic entities только для non-commercial purposes; изображения происходят с Pexels ([official dataset repository](https://github.com/supervisely-ecosystem/persons#license)). | Не использовать для commercial-compatible public fixture set. |
| Fashionpedia | Annotations/ontology — CC BY 4.0, но Fashionpedia не владеет изображениями; права зависят от Flickr, Unsplash, Burst, Freestocks, Kaboompics и Pexels, ответственность переложена на пользователя ([official terms](https://fashionpedia.github.io/home/data_license.html)). | Не копировать изображения wholesale. Возможна только пофайловая проверка исходного владельца и текущих условий; Open Images проще и прозрачнее. |
| Unsplash Dataset | Lite разрешён для internal ML use, но terms запрещают disclose/publish/redistribute any portion of licensed data ([official Dataset Terms](https://github.com/unsplash/datasets/blob/master/TERMS.md#3-restrictions)). | Нельзя помещать subset в публичный GitHub repo. |
| Обычные Unsplash images | Текущие Terms запрещают использовать images в ML/AI datasets вне специального Unsplash Dataset program ([official Terms](https://unsplash.com/terms)). | Не собирать новые fixture images с Unsplash. Старые CC0-файлы на Commons допустимы только при доказанном дореформенном CC0 release. |
| Pexels | Текущие Terms запрещают неавторизованный data mining/collection, включая ML datasets; официальный FAQ прямо говорит не использовать API для training/evaluation datasets без разрешения ([official Terms explanation](https://help.pexels.com/hc/en-us/articles/900005880463-What-are-the-Terms-and-Conditions)). | Не использовать для калибровочной выборки без письменного разрешения Pexels. |

## Предлагаемый manifest для будущих fixtures

Для каждого исходного изображения и mask-файла хранить одну запись:

```yaml
- id: oi-validation-<ImageID>-shirt
  source_page: https://...
  original_author: "..."
  original_title: "..."
  image_license: CC-BY-2.0
  image_license_url: https://creativecommons.org/licenses/by/2.0/
  annotation_source: Open Images V6
  annotation_license: CC-BY-4.0
  modifications: "resized to <=768px; JPEG re-encoded; mask converted to binary PNG"
  license_checked_at: 2026-08-26
  sha256: "..."
  subject_release: "not supplied; face not identifiable" # либо "project release on file"
  intended_case: upper_semantic_leakage
```

Отдельный fixture README должен прямо говорить, что основная лицензия Wardrowbe не переопределяет лицензии изображений и annotations.

## Primary sources

### GitHub

- [GitHub Docs — Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- [GitHub Docs — Triggering a workflow and filters](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)
- [GitHub Docs — Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [GitHub Docs — GITHUB_TOKEN event suppression](https://docs.github.com/en/actions/concepts/security/github_token#when-github_token-triggers-workflow-runs)
- [GitHub Docs — Skipping workflow runs](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/skipping-workflow-runs)
- [GitHub Docs — Repository Actions settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository)
- [GitHub Docs — REST Actions permissions](https://docs.github.com/en/rest/actions/permissions)
- [GitHub Docs — REST workflow runs](https://docs.github.com/en/rest/actions/workflow-runs)
- [GitHub Status API](https://www.githubstatus.com/api/v2/status.json) and [incident API](https://www.githubstatus.com/api/v2/incidents.json)
- Wardrowbe official API: [repository](https://api.github.com/repos/theEvgene/wardrowbe), [workflows](https://api.github.com/repos/theEvgene/wardrowbe/actions/workflows), [push runs](https://api.github.com/repos/theEvgene/wardrowbe/actions/runs?event=push&per_page=20), [manual runs](https://api.github.com/repos/theEvgene/wardrowbe/actions/runs?event=workflow_dispatch&per_page=20), [events](https://api.github.com/repos/theEvgene/wardrowbe/events?per_page=30)

### Images and datasets

- [Open Images V7 description and licenses](https://storage.googleapis.com/openimages/web/factsfigures_v7.html)
- [Open Images official downloads and data formats](https://storage.googleapis.com/openimages/web/download.html)
- [Open Images segmentation class IDs](https://storage.googleapis.com/openimages/v5/classes-segmentation.txt) and [class descriptions](https://storage.googleapis.com/openimages/v5/class-descriptions-boxable.csv)
- [Creative Commons CC BY 2.0](https://creativecommons.org/licenses/by/2.0/), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), and [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)
- [Wikimedia Commons reuse guidance](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia/en) and the three file pages linked above
- [DeepFashion official terms](https://mmlab.ie.cuhk.edu.hk/projects/DeepFashion.html)
- [Supervisely Person Dataset official repository/license](https://github.com/supervisely-ecosystem/persons#license)
- [Fashionpedia official data license](https://fashionpedia.github.io/home/data_license.html)
- [Unsplash Dataset official terms](https://github.com/unsplash/datasets/blob/master/TERMS.md)
- [Unsplash official Terms](https://unsplash.com/terms)
- [Pexels official Terms explanation](https://help.pexels.com/hc/en-us/articles/900005880463-What-are-the-Terms-and-Conditions)
