#!/usr/bin/env python3
"""Write guides/whats-new/<lang>.md from the app's Google Play release notes.

    python3 tools/whatsnew.py ../dil-okuma-app/docs

Each release-notes-<name>+<build>.txt in that folder holds ten <xx-XX>…</xx-XX> blocks:
a header line and "• " bullets. RELEASES says which build's notes stand for a version
name and the day that version reached production (docs/changelog.md in the app repo),
newest first. Re-run after every production release, then `python3 build.py`.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "guides" / "whats-new"

RELEASES = [  # version name, release-notes file stem, production date
    ("1.3.0", "1.3.0+42", "2026-11-07"),
    ("1.2.1", "1.2.1+40", "2026-11-01"),
    ("1.2.0", "1.2.0+37", "2026-10-28"),
    ("1.1.0", "1.1.0+35", "2026-10-21"),
]
TAGS = {"en": "en-US", "az": "az-AZ", "tr": "tr-TR", "de": "de-DE", "es": "es-ES",
        "fr": "fr-FR", "it": "it-IT", "ru": "ru-RU", "pl": "pl-PL", "pt": "pt-BR"}
MONTHS = {
    "en": "January February March April May June July August September October November December",
    "az": "yanvar fevral mart aprel may iyun iyul avqust sentyabr oktyabr noyabr dekabr",
    "tr": "Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık",
    "de": "Januar Februar März April Mai Juni Juli August September Oktober November Dezember",
    "es": "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre",
    "fr": "janvier février mars avril mai juin juillet août septembre octobre novembre décembre",
    "it": "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre",
    "ru": "января февраля марта апреля мая июня июля августа сентября октября ноября декабря",
    "pl": "stycznia lutego marca kwietnia maja czerwca lipca sierpnia września października listopada grudnia",
    "pt": "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro",
}


def fmt_date(lang: str, iso: str) -> str:
    y, m, d = (int(x) for x in iso.split("-"))
    month = MONTHS[lang].split()[m - 1]
    if lang == "de":
        return f"{d}. {month} {y}"
    if lang in ("es", "pt"):
        day = "1º" if (d == 1 and lang == "pt") else str(d)
        return f"{day} de {month} de {y}"
    if lang == "fr":
        return f"{'1er' if d == 1 else d} {month} {y}"
    if lang == "it":
        return f"{'1º' if d == 1 else d} {month} {y}"
    return f"{d} {month} {y}"


T = {
 "en": dict(
    title="What's new in Biblyx: version history", h1="What's new in Biblyx", path="whats-new",
    description="Every Biblyx update since 1.1.0, in the words of its Google Play release notes, with the day it reached users. Current version: {v} ({date}).",
    slogan="Learn languages by reading your own books",
    cta="Open an EPUB, PDF or TXT, or paste a text. Tap a word, see what it means in that sentence, save it and review it later.",
    intro="Biblyx ships a new version every one to two weeks. This page lists what each version brought, in the words of its Google Play release notes, with the day it reached everyone. The current version is **{v}**, in production since {date}. What the app is for doesn't change between versions: **Learn languages by reading your own books**.",
    version="Version {v}, {date}", how_h="How updates arrive",
    how="Google Play installs updates by itself when auto-update is on; otherwise the Biblyx page on Google Play shows an Update button. The version on your phone is shown on the About screen inside the app. Updating never touches your saved words, flashcards, progress, bookmarks or highlights.",
    faq_h="Frequently asked questions",
    faq=[("How often is Biblyx updated?", "Usually every one to two weeks; fixes go out faster. A version's notes appear here on the day it reaches Google Play."),
         ("Do I lose my saved words when I update?", "No. Saved words, flashcards, review progress, bookmarks and highlights stay on your device, and with an account they are synced as well."),
         ("Where do I report a problem or ask for a feature?", "Write to support@biblyx.com. Every message is read, and fixes usually go into the next version."),
         ("Is there an iPhone version?", "Not yet. Biblyx is on Android through Google Play; an iOS version is planned, with no date.")]),
 "az": dict(
    title="Biblyx-də yeniliklər: versiya tarixçəsi", h1="Biblyx-də yeniliklər", path="yenilikler",
    description="1.1.0-dan bəri hər Biblyx yeniləməsi, Google Play buraxılış qeydlərinin öz sözləri ilə və istifadəçilərə çatdığı günlə. Hazırkı versiya: {v} ({date}).",
    slogan="Öz kitablarını oxuyaraq dil öyrən",
    cta="EPUB, PDF və ya TXT faylını aç, ya da bir mətni yapışdır. Sözə toxun, həmin cümlədəki mənasını gör, saxla və sonra təkrar et.",
    intro="Biblyx bir-iki həftədən bir yeni versiya çıxarır. Bu səhifədə hər versiyanın nə gətirdiyi Google Play buraxılış qeydlərinin öz sözləri ilə, hamıya çatdığı günlə birlikdə yazılıb. Hazırkı versiya **{v}**-dır, {date} tarixindən istehsaldadır. Tətbiqin məqsədi versiyadan versiyaya dəyişmir: **Öz kitablarını oxuyaraq dil öyrən**.",
    version="Versiya {v}, {date}", how_h="Yeniləmələr necə gəlir",
    how="Avtomatik yeniləmə açıqdırsa, Google Play yeniləməni özü quraşdırır; deyilsə, Biblyx-in Google Play səhifəsində “Yenilə” düyməsi görünür. Telefonundakı versiya tətbiqin içindəki “Haqqında” ekranında yazılıb. Yeniləmə saxladığın sözlərə, kartlara, gedişata, əlfəcinlərə və işarələmələrə toxunmur.",
    faq_h="Tez-tez verilən suallar",
    faq=[("Biblyx nə qədər tez-tez yenilənir?", "Adətən bir-iki həftədən bir; düzəlişlər daha tez çıxır. Versiyanın qeydləri Google Play-ə çatdığı gün burada görünür."),
         ("Yeniləyəndə saxladığım sözlər itirmi?", "Yox. Saxlanan sözlər, kartlar, təkrar gedişatı, əlfəcinlər və işarələmələr cihazında qalır, hesabla isə həm də sinxronlaşır."),
         ("Problemi hara yazım, təklifi necə göndərim?", "support@biblyx.com ünvanına yaz. Hər məktub oxunur, düzəlişlər adətən növbəti versiyaya düşür."),
         ("iPhone versiyası varmı?", "Hələ yox. Biblyx Google Play-də, Android üçündür; iOS versiyası planlaşdırılır, tarix yoxdur.")]),
 "tr": dict(
    title="Biblyx'teki yenilikler: sürüm geçmişi", h1="Biblyx'teki yenilikler", path="yenilikler",
    description="1.1.0'dan bu yana her Biblyx güncellemesi, Google Play sürüm notlarının kendi sözleriyle ve kullanıcılara ulaştığı günle. Güncel sürüm: {v} ({date}).",
    slogan="Kendi kitaplarını okuyarak dil öğren",
    cta="EPUB, PDF ya da TXT dosyanı aç veya bir metin yapıştır. Kelimeye dokun, o cümledeki anlamını gör, kaydet ve sonra tekrar et.",
    intro="Biblyx bir iki haftada bir yeni sürüm çıkarır. Bu sayfa her sürümün ne getirdiğini Google Play sürüm notlarının kendi sözleriyle, herkese ulaştığı günle birlikte listeler. Güncel sürüm **{v}**, {date} tarihinden beri yayında. Uygulamanın amacı sürümden sürüme değişmez: **Kendi kitaplarını okuyarak dil öğren**.",
    version="Sürüm {v}, {date}", how_h="Güncellemeler nasıl gelir",
    how="Otomatik güncelleme açıksa Google Play güncellemeyi kendisi kurar; değilse Biblyx'in Google Play sayfasında “Güncelle” düğmesi görünür. Telefonundaki sürüm, uygulamanın içindeki “Hakkında” ekranında yazar. Güncelleme kayıtlı kelimelerine, kartlarına, ilerlemene, yer imlerine ve vurgularına dokunmaz.",
    faq_h="Sık sorulan sorular",
    faq=[("Biblyx ne sıklıkla güncellenir?", "Genellikle bir iki haftada bir; düzeltmeler daha hızlı çıkar. Bir sürümün notları Google Play'e ulaştığı gün burada görünür."),
         ("Güncelleyince kayıtlı kelimelerim silinir mi?", "Hayır. Kayıtlı kelimeler, kartlar, tekrar ilerlemesi, yer imleri ve vurgular cihazında kalır; hesapla ayrıca eşitlenir."),
         ("Bir sorunu nereye bildiririm, özellik nasıl isterim?", "support@biblyx.com adresine yaz. Her mesaj okunur, düzeltmeler genellikle bir sonraki sürüme girer."),
         ("iPhone sürümü var mı?", "Henüz yok. Biblyx Google Play'de, Android için; iOS sürümü planlanıyor, tarih yok.")]),
 "de": dict(
    title="Neu in Biblyx: alle Versionen", h1="Neu in Biblyx", path="neuigkeiten",
    description="Jedes Biblyx-Update seit 1.1.0 im Wortlaut der Google-Play-Versionshinweise, mit dem Tag, an dem es die Nutzer erreicht hat. Aktuell: {v} ({date}).",
    slogan="Sprachen lernen beim Lesen deiner eigenen Bücher",
    cta="Öffne eine EPUB-, PDF- oder TXT-Datei oder füge einen Text ein. Tippe auf ein Wort, sieh seine Bedeutung in diesem Satz, speichere es und wiederhole es später.",
    intro="Biblyx bekommt alle ein bis zwei Wochen eine neue Version. Diese Seite listet, was jede Version gebracht hat, im Wortlaut der Versionshinweise bei Google Play und mit dem Tag, an dem sie alle erreicht hat. Die aktuelle Version ist **{v}**, in Produktion seit dem {date}. Wozu die App da ist, ändert sich von Version zu Version nicht: **Sprachen lernen beim Lesen deiner eigenen Bücher**.",
    version="Version {v}, {date}", how_h="Wie Updates ankommen",
    how="Google Play installiert Updates von selbst, wenn automatische Updates eingeschaltet sind; sonst zeigt die Biblyx-Seite bei Google Play einen Knopf „Aktualisieren“. Welche Version auf deinem Telefon ist, steht auf dem Bildschirm „Über“ in der App. Ein Update rührt deine gespeicherten Wörter, Karten, Fortschritte, Lesezeichen und Markierungen nicht an.",
    faq_h="Häufige Fragen",
    faq=[("Wie oft wird Biblyx aktualisiert?", "Meist alle ein bis zwei Wochen; Fehlerbehebungen kommen schneller. Die Hinweise einer Version erscheinen hier an dem Tag, an dem sie Google Play erreicht."),
         ("Verliere ich beim Update meine gespeicherten Wörter?", "Nein. Gespeicherte Wörter, Karten, Lernfortschritt, Lesezeichen und Markierungen bleiben auf deinem Gerät, mit einem Konto werden sie zusätzlich abgeglichen."),
         ("Wo melde ich ein Problem oder wünsche mir eine Funktion?", "Schreib an support@biblyx.com. Jede Nachricht wird gelesen, Korrekturen kommen meist in die nächste Version."),
         ("Gibt es eine iPhone-Version?", "Noch nicht. Biblyx gibt es für Android bei Google Play; eine iOS-Version ist geplant, ohne Termin.")]),
 "es": dict(
    title="Novedades de Biblyx: historial de versiones", h1="Novedades de Biblyx", path="novedades",
    description="Cada actualización de Biblyx desde la 1.1.0, con sus notas de Google Play y el día en que llegó a los usuarios. Versión actual: {v} ({date}).",
    slogan="Aprende idiomas leyendo tus propios libros",
    cta="Abre un EPUB, PDF o TXT, o pega un texto. Toca una palabra, mira qué significa en esa frase, guárdala y repásala después.",
    intro="Biblyx publica una versión nueva cada una o dos semanas. Esta página recoge lo que trajo cada versión, con las palabras de sus notas en Google Play y el día en que llegó a todo el mundo. La versión actual es la **{v}**, en producción desde el {date}. Para qué sirve la app no cambia de una versión a otra: **Aprende idiomas leyendo tus propios libros**.",
    version="Versión {v}, {date}", how_h="Cómo llegan las actualizaciones",
    how="Google Play instala las actualizaciones solo si tienes activada la actualización automática; si no, la página de Biblyx en Google Play muestra el botón Actualizar. La versión que tienes aparece en la pantalla Acerca de, dentro de la app. Actualizar no toca tus palabras guardadas, tarjetas, progreso, marcadores ni subrayados.",
    faq_h="Preguntas frecuentes",
    faq=[("¿Cada cuánto se actualiza Biblyx?", "Normalmente cada una o dos semanas; las correcciones salen antes. Las notas de una versión aparecen aquí el día en que llega a Google Play."),
         ("¿Pierdo mis palabras guardadas al actualizar?", "No. Las palabras guardadas, las tarjetas, el progreso de repaso, los marcadores y los subrayados se quedan en tu dispositivo, y con una cuenta además se sincronizan."),
         ("¿Dónde informo de un problema o pido una función?", "Escribe a support@biblyx.com. Se lee cada mensaje, y las correcciones suelen entrar en la siguiente versión."),
         ("¿Hay versión para iPhone?", "Todavía no. Biblyx está en Android a través de Google Play; la versión para iOS está prevista, sin fecha.")]),
 "fr": dict(
    title="Nouveautés de Biblyx : historique des versions", h1="Nouveautés de Biblyx", path="nouveautes",
    description="Chaque mise à jour de Biblyx depuis la 1.1.0, avec ses notes Google Play et le jour où elle a atteint les utilisateurs. Version actuelle : {v} ({date}).",
    slogan="Apprenez les langues en lisant vos propres livres",
    cta="Ouvrez un EPUB, un PDF ou un TXT, ou collez un texte. Touchez un mot, voyez son sens dans cette phrase, enregistrez-le et révisez-le plus tard.",
    intro="Biblyx sort une nouvelle version toutes les une à deux semaines. Cette page liste ce que chaque version a apporté, dans les mots de ses notes de version sur Google Play, avec le jour où elle a atteint tout le monde. La version actuelle est la **{v}**, en production depuis le {date}. Ce à quoi sert l'application ne change pas d'une version à l'autre : **Apprenez les langues en lisant vos propres livres**.",
    version="Version {v}, {date}", how_h="Comment arrivent les mises à jour",
    how="Google Play installe les mises à jour tout seul si la mise à jour automatique est activée ; sinon, la page de Biblyx sur Google Play affiche un bouton Mettre à jour. La version installée sur votre téléphone est indiquée sur l'écran À propos, dans l'application. Une mise à jour ne touche ni vos mots enregistrés, ni vos cartes, votre progression, vos signets ou vos surlignages.",
    faq_h="Questions fréquentes",
    faq=[("À quelle fréquence Biblyx est-il mis à jour ?", "En général toutes les une à deux semaines ; les correctifs sortent plus vite. Les notes d'une version paraissent ici le jour où elle atteint Google Play."),
         ("Est-ce que je perds mes mots enregistrés en mettant à jour ?", "Non. Mots enregistrés, cartes, progression des révisions, signets et surlignages restent sur votre appareil, et avec un compte ils sont aussi synchronisés."),
         ("Où signaler un problème ou demander une fonction ?", "Écrivez à support@biblyx.com. Chaque message est lu, et les correctifs arrivent le plus souvent dans la version suivante."),
         ("Existe-t-il une version iPhone ?", "Pas encore. Biblyx est sur Android via Google Play ; une version iOS est prévue, sans date.")]),
 "it": dict(
    title="Novità di Biblyx: cronologia delle versioni", h1="Novità di Biblyx", path="novita",
    description="Ogni aggiornamento di Biblyx dalla 1.1.0, con le sue note su Google Play e il giorno in cui è arrivato agli utenti. Versione attuale: {v} ({date}).",
    slogan="Impara le lingue leggendo i tuoi libri",
    cta="Apri un EPUB, PDF o TXT, oppure incolla un testo. Tocca una parola, guarda cosa significa in quella frase, salvala e ripassala più tardi.",
    intro="Biblyx esce con una versione nuova ogni una o due settimane. Questa pagina elenca cosa ha portato ogni versione, con le parole delle sue note su Google Play e il giorno in cui è arrivata a tutti. La versione attuale è la **{v}**, in produzione dal {date}. A cosa serve l'app non cambia da una versione all'altra: **Impara le lingue leggendo i tuoi libri**.",
    version="Versione {v}, {date}", how_h="Come arrivano gli aggiornamenti",
    how="Google Play installa gli aggiornamenti da solo se l'aggiornamento automatico è attivo; altrimenti la pagina di Biblyx su Google Play mostra il pulsante Aggiorna. La versione sul tuo telefono è indicata nella schermata Informazioni dentro l'app. Un aggiornamento non tocca parole salvate, carte, progressi, segnalibri ed evidenziazioni.",
    faq_h="Domande frequenti",
    faq=[("Ogni quanto si aggiorna Biblyx?", "Di solito ogni una o due settimane; le correzioni escono prima. Le note di una versione compaiono qui il giorno in cui arriva su Google Play."),
         ("Perdo le parole salvate aggiornando?", "No. Parole salvate, carte, progressi del ripasso, segnalibri ed evidenziazioni restano sul tuo dispositivo, e con un account vengono anche sincronizzati."),
         ("Dove segnalo un problema o chiedo una funzione?", "Scrivi a support@biblyx.com. Ogni messaggio viene letto, e le correzioni di solito entrano nella versione successiva."),
         ("Esiste una versione per iPhone?", "Non ancora. Biblyx è su Android tramite Google Play; la versione iOS è in programma, senza data.")]),
 "ru": dict(
    title="Что нового в Biblyx: история версий", h1="Что нового в Biblyx", path="chto-novogo",
    description="Каждое обновление Biblyx начиная с 1.1.0 — словами его заметок в Google Play и с днём, когда оно дошло до пользователей. Текущая версия: {v} ({date}).",
    slogan="Учите языки, читая свои книги",
    cta="Откройте EPUB, PDF или TXT либо вставьте текст. Нажмите на слово, посмотрите его значение в этом предложении, сохраните и повторите позже.",
    intro="Новая версия Biblyx выходит раз в одну-две недели. На этой странице перечислено, что принесла каждая версия, словами её заметок о выпуске в Google Play и с днём, когда она дошла до всех. Текущая версия — **{v}**, в продакшене с {date}. Назначение приложения от версии к версии не меняется: **Учите языки, читая свои книги**.",
    version="Версия {v}, {date}", how_h="Как приходят обновления",
    how="Google Play устанавливает обновления сам, если включено автообновление; иначе на странице Biblyx в Google Play появляется кнопка «Обновить». Какая версия стоит на вашем телефоне, видно на экране «О приложении» внутри Biblyx. Обновление не трогает сохранённые слова, карточки, прогресс, закладки и выделения.",
    faq_h="Частые вопросы",
    faq=[("Как часто обновляется Biblyx?", "Обычно раз в одну-две недели; исправления выходят быстрее. Заметки версии появляются здесь в день, когда она доходит до Google Play."),
         ("Пропадут ли сохранённые слова при обновлении?", "Нет. Сохранённые слова, карточки, прогресс повторения, закладки и выделения остаются на устройстве, а с аккаунтом ещё и синхронизируются."),
         ("Куда сообщить о проблеме или попросить функцию?", "Напишите на support@biblyx.com. Каждое письмо читается, исправления обычно попадают в следующую версию."),
         ("Есть ли версия для iPhone?", "Пока нет. Biblyx доступен для Android в Google Play; версия для iOS планируется, даты нет.")]),
 "pl": dict(
    title="Nowości w Biblyx: historia wersji", h1="Nowości w Biblyx", path="nowosci",
    description="Każda aktualizacja Biblyx od wersji 1.1.0, słowami jej opisu w Google Play i z dniem, w którym dotarła do użytkowników. Aktualna wersja: {v} ({date}).",
    slogan="Ucz się języków, czytając własne książki",
    cta="Otwórz plik EPUB, PDF lub TXT albo wklej tekst. Dotknij słowa, zobacz jego znaczenie w tym zdaniu, zapisz je i powtórz później.",
    intro="Nowa wersja Biblyx wychodzi co tydzień lub dwa. Ta strona wymienia, co przyniosła każda wersja, słowami jej opisu w Google Play i z dniem, w którym dotarła do wszystkich. Aktualna wersja to **{v}**, w produkcji od {date}. To, do czego służy aplikacja, nie zmienia się z wersji na wersję: **Ucz się języków, czytając własne książki**.",
    version="Wersja {v}, {date}", how_h="Jak przychodzą aktualizacje",
    how="Google Play instaluje aktualizacje sam, jeśli włączone są aktualizacje automatyczne; w przeciwnym razie na stronie Biblyx w Google Play pojawia się przycisk Aktualizuj. Którą wersję masz w telefonie, widać na ekranie „O aplikacji” w Biblyx. Aktualizacja nie rusza zapisanych słów, fiszek, postępów, zakładek ani zakreśleń.",
    faq_h="Częste pytania",
    faq=[("Jak często Biblyx jest aktualizowany?", "Zwykle co tydzień lub dwa; poprawki wychodzą szybciej. Opis wersji pojawia się tutaj w dniu, w którym trafia do Google Play."),
         ("Czy przy aktualizacji stracę zapisane słowa?", "Nie. Zapisane słowa, fiszki, postęp powtórek, zakładki i zakreślenia zostają na urządzeniu, a z kontem są też synchronizowane."),
         ("Gdzie zgłosić problem albo poprosić o funkcję?", "Napisz na support@biblyx.com. Każda wiadomość jest czytana, a poprawki zwykle trafiają do następnej wersji."),
         ("Czy jest wersja na iPhone'a?", "Jeszcze nie. Biblyx jest na Androida w Google Play; wersja na iOS jest w planach, bez daty.")]),
 "pt": dict(
    title="Novidades do Biblyx: histórico de versões", h1="Novidades do Biblyx", path="novidades",
    description="Cada atualização do Biblyx desde a 1.1.0, nas palavras das notas do Google Play e com o dia em que chegou aos usuários. Versão atual: {v} ({date}).",
    slogan="Aprenda idiomas lendo seus próprios livros",
    cta="Abra um EPUB, PDF ou TXT, ou cole um texto. Toque em uma palavra, veja o que ela significa naquela frase, salve e revise depois.",
    intro="O Biblyx lança uma versão nova a cada uma ou duas semanas. Esta página lista o que cada versão trouxe, nas palavras das notas de lançamento do Google Play, com o dia em que chegou a todo mundo. A versão atual é a **{v}**, em produção desde {date}. Para que o app serve não muda de uma versão para outra: **Aprenda idiomas lendo seus próprios livros**.",
    version="Versão {v}, {date}", how_h="Como as atualizações chegam",
    how="O Google Play instala as atualizações sozinho quando a atualização automática está ligada; senão, a página do Biblyx no Google Play mostra o botão Atualizar. A versão no seu celular aparece na tela Sobre, dentro do app. Atualizar não mexe nas suas palavras salvas, cards, progresso, marcadores ou destaques.",
    faq_h="Perguntas frequentes",
    faq=[("Com que frequência o Biblyx é atualizado?", "Em geral a cada uma ou duas semanas; correções saem mais rápido. As notas de uma versão aparecem aqui no dia em que ela chega ao Google Play."),
         ("Perco minhas palavras salvas ao atualizar?", "Não. Palavras salvas, cards, progresso de revisão, marcadores e destaques ficam no seu aparelho, e com uma conta também são sincronizados."),
         ("Onde relato um problema ou peço uma função?", "Escreva para support@biblyx.com. Toda mensagem é lida, e as correções costumam entrar na versão seguinte."),
         ("Tem versão para iPhone?", "Ainda não. O Biblyx está no Android pelo Google Play; a versão para iOS está planejada, sem data.")]),
}


def bullets(notes_dir: Path, stem: str, lang: str) -> list:
    text = (notes_dir / f"release-notes-{stem}.txt").read_text(encoding="utf-8")
    tag = TAGS[lang]
    m = re.search(rf"<{tag}>\n(.*?)</{tag}>", text, re.S)
    if not m:
        sys.exit(f"no <{tag}> block in release-notes-{stem}.txt")
    lines = [l.strip() for l in m.group(1).splitlines() if l.strip()]
    items = [l[1:].strip() for l in lines if l.startswith("•")]
    if not items:
        sys.exit(f"no bullets for {tag} in release-notes-{stem}.txt")
    return items


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    notes_dir = Path(sys.argv[1]).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    cur_v, _, cur_date = RELEASES[0]
    for lang, t in T.items():
        date = fmt_date(lang, cur_date)
        fm = "\n".join([
            "---",
            f"title: {t['title']}",
            f"h1: {t['h1']}",
            f"description: {t['description'].format(v=cur_v, date=date)}",
            f"path: {t['path']}",
            f"date: {cur_date}",
            f"slogan: {t['slogan']}",
            f"cta: {t['cta']}",
            "short: yes",
            "---",
        ])
        parts = [fm, "", t["intro"].format(v=cur_v, date=date), ""]
        for v, stem, iso in RELEASES:
            parts.append("## " + t["version"].format(v=v, date=fmt_date(lang, iso)))
            parts.append("")
            parts.extend(f"- {b}" for b in bullets(notes_dir, stem, lang))
            parts.append("")
        parts += ["## " + t["how_h"], "", t["how"], "", "## " + t["faq_h"], ""]
        for q, a in t["faq"]:
            parts += [f"### {q}", "", a, ""]
        (OUT / f"{lang}.md").write_text("\n".join(parts), encoding="utf-8")
        print(f"wrote guides/whats-new/{lang}.md")


if __name__ == "__main__":
    main()
