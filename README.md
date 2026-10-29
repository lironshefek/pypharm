# PyPharm - ניהול קטלוג, מלאי מבוזר וניוד סחורה ברשת פארם וטיפוח

<div dir="rtl">

## 1. הצעת הפרויקט

> **PyPharm** - מערכת לניהול קטלוג מוצרים, מעקב הזמנות ניוד, בקרת הרשאות עובדים ומלאי מבוזר בין סניפי ומחסני רשת פארם וטיפוח.

### הצורך העסקי והבעיה
רשת פארם מתמודדת עם פערי ביקוש בין סניפים, שיוצרים חוסר במוצרי טיפוח מבוקשים בחנות אחת ועודפים באחרת.

המערכת מרכזת תמונת מלאי בזמן אמת, מפקחת על תהליכי הניוד ומאפשרת למנהלים ולעובדים מורשים לצפות בהזמנות הפתוחות ולנהל את תנועת הסחורה בצורה מבוקרת.

כך ניתן לנייד פריטים במהירות בין סניפים, למנוע אובדן מכירות ולשמור על מדפים מלאים.

---

### משתמשי המערכת ותפקידם

* **מנהל/ת סניף:**  
  צופה בהזמנות הניוד הפתוחות, מנהל/ת את קבלת הסחורה למדפים, מעדכן/ת חוסרים ומגיש/ה בקשות להעברת פריטים מסניפים אחרים או מהמחסן.

* **מנהל/ת מחסן:**  
  מנהל/ת את המלאי המרכזי, מלקט/ת ואורז/ת הזמנות ניוד לסניפים לפי בקשות מאושרות, ומעדכן/ת סטטוס משלוחים.

* **מנהל/ת לוגיסטיקה / רשת:**  
  צופה בתמונת המלאי הכוללת, מאשר/ת העברות רגישות, מפקח/ת על הרשאות העובדים ומבצע/ת ביקורת תקינות נתונים.

---

### התהליך העסקי המרכזי
**השלמת חוסרים וניוד סחורה לסניף:**  
כאשר מנהל הסניף מזהה שמוצר צפוי להיגמר במדף (מעבר מתחת ל- 'min_threshold'),
הוא פותח בקשת ניוד מהירה ('TransferOrder').

הבקשה נכנסת לתור תיעדוף דחיפות (`PriorityTransferQueue`).  

ברגע שהבקשה מטופלת, עובד מורשה משריין את המלאי במקור, הופך את סטטוס ההזמנה ל-`IN_TRANSIT`, ועם הגעת המשלוח ליעד הסטטוס משתנה ל- `DELIVERED`
והמלאי מתעדכן אוטומטית בשני הצדדים.

---

### זרימת המידע

* **מידע נכנס:**  
  פרטי מוצרים (מק"ט, שם, מותג, מחיר, תוקף/משקל), מיקומי אחסון, רמות מלאי קיימות, קטלוג עובדים ותפקידיהם, ובקשות ניוד פנימיות.

* **מי יוצר ומעדכן:**  
  מנהלי הרשת מעדכנים מוצרים ועובדים; מנהלי הסניפים מעדכנים מלאי פיזי ופותחים בקשות ניוד; עובדי מחסן מורשים מעדכנים סטטוס ניודים.

* **מידע מופק:**  
  תמונת מלאי עדכנית (זמין/שוריין/בדרך), התראות על חוסרים במדף (`is_low_stock`), יומן ביקורת שינויי סטטוס (Audit Log), ודוח חריגות ויושרה עסקי.

---

### הערך העסקי

* **שליטה ובקרה על סחורה:**  
  מעקב שקוף אחר כמויות מלאי והזמנות ניוד מונע בלבול וחוסר ודאות בין החנויות.

* **שיפור חוויית הלקוח:**  
  זמינות רציפה של מוצרים מבוקשים ומניעת חוסר מלאי.

* **איזון מלאים חסכוני:**  
  ניצול יעיל של סחורה שכבר קיימת ברשת ומניעת מצב שבו מוצרים נשארים ללא שימוש.

---

### ישויות מרכזיות וקשרים

* **מוצר (`Product`):**  
 (מוצר מדף סטנדרטי) מחלקה אבסטרקטית המיוצגת ע"י `PerishableProduct` 
  (מוצר מתכלה/בקירור)`StandardProduct`.

* **מיקום (`Location`):**  
  סניף מכירה או מחסן מרכזי.

* **מלאי מיקום (`InventoryItem`):**  
  מקשר בין מוצר למיקום, ומכיל כמויות זמינות, משוריינות ובדרך.

* **בקשת ניוד (`TransferOrder`):**  
  מכילה רשימה של פריטי ניוד (`TransferOrderItem`) ומקושרת לעובד מטפל.

* **עובד (`Employee`):**  
  בעל תפקיד מוגדר ברשת (מנהל לוגיסטיקה, מנהל מחסן, עובד מחסן, רוקח, קופאי).

* **רכיב הרשאות (`OrderActionAuthorizer`):**  
  מפקח על הפעולות שכל עובד מורשה לבצע.

---

### תרחישי שימוש מרכזיים (Use Cases)

1. **איתור מהיר, שיריון והשלמת חוסר:**  
זיהוי מוצר בחוסר בסניף, פתיחת בקשת ניוד, שיריון המלאי במחסן המרכזי והעברתו לסניף.

2. **ניהול הרשאות ואימות יושרה עסקי:**  
   ניסיון עדכון סטטוס ניוד ע"י עובד (למשל קופאי) נחסם ע"י ה-Authorizer,
    והמערכת מפיקה דוח חריגות המזהה הזמנות המשויכות לעובדים לא פעילים או לא קיימים.

---

### רעיון להרחבה עתידית
**מודול חיווי אוטומטי לחידוש מלאי (Auto-Replenishment Engine):**  
המערכת תזהה אוטומטית סניפים שנמצאים בחוסר קריטי, ותייצר עבורם הצעת הזמנת ניוד מומלצת מהמחסן המרכזי על בסיס נתוני צריכה היסטוריים.

---

## 2. מפת הקבצים בפועל

```
pypharm/  (repository root)
│
├── pypharm/                           # חבילת Python (package)
│   ├── __init__.py                    # הגדרת החבילה, ייצוא כל המודולים
│   ├── factories.py                    # ProductFactory ליצירת סוג המוצר לפי רשומת JSONL
│   ├── observers.py                    # אירועי אישור בסיכון מזג אוויר גבוה ומאזינים
│   ├── models.py                      # מחלקות OOP, הרכבה, הורשה, פולימורפיזם, הרשאות ועובדים
│   ├── processing.py                  # מבני נתונים, תורים, Comprehensions, לוגיקה עסקית ומיון
│   ├── iterators.py                   # איטרטורים מותאמים, גנרטורים ו-Lazy Pipeline
│   ├── context_managers.py            # ניהול משאבים, נעילת מיקומים בזמן טיפול וטיפול בחריגות
│   ├── repository.py                  # טעינת קבצי JSONL, המרה לאובייקטים ואימות נתונים
│   └── reports.py                     # הפקת דוח עסקי
│
├── data/                              # קבצי הנתונים הסינתטיים (JSONL)
│   ├── sample_data.jsonl              # קטלוג מוצרים, מיקומים ועובדים
│   └── inventory_data.jsonl           # פריטי מלאי ברשת והזמנות ניוד
│
├── main.py                            # תרחיש ההדגמה המלא של המערכת
├── README.md                          # תיעוד הפרויקט המלא (קובץ זה)
├── AI_USAGE.md                        # תיעוד שימוש ב-AI (פרומפטים, בדיקות ותיקונים)
├── pyproject.toml                     # הגדרות הפרויקט והתלויות
└── .gitignore                         # קבצים להתעלמות ב-Git
```


---

## 3. תת-המערכת המורחבת (הרחבה לקבוצה של 4 סטודנטיות)

כחלק מהדרישות לקבוצה בת 4 סטודנטיות, תוכננה ומומשה תת-מערכת עסקית ל
**ניהול עובדים, בקרת הרשאות ואימות יושרת נתונים (Audit & Integrity Control Subsystem)**.

### הישויות החדשות שהתווספו (`pypharm/models.py`)
1. **`Employee`:** מייצגת עובד ברשת.
 מכילה מזהה, שם, תפקיד (`LOGISTICS_MANAGER`, `WAREHOUSE_MANAGER`, `WAREHOUSE_WORKER`, `PHARMACIST`, `CASHIER`) וסטטוס פעילות (`is_active`).

2. **`OrderActionAuthorizer`:** מנגנון אבטחה והרשאות שמנהל לוגיקת הרשאות לפי תפקיד העובד (RBAC), מאשר שינויי סטטוס בהזמנות ניוד, ומתעד כל פעולה ביומן ביקורת פנימי (`action_history`).

### הפעולות והתהליכים העסקיים החדשים
1. **ניהול סטטוס פעילות עובדים:** היכולת לאקטב/לנטרל עובדים במערכת.

2. **אימות הרשאות דינמי (Authorization Check):** חסימת ביצוע פעולות ניוד 
(כגון `DISPATCH` או `DELIVER`) אם העובד המבצע אינו בעל תפקיד מתאים או אינו פעיל.

3. **תהליך אימות יושרת נתונים המקושר למערכת המרכזית:** סריקת כל הזמנות הניוד הפעילות והשוואתן מול קטלוג העובדים.

### קובץ הנתונים הנוסף והקישור ביניהם
* **`data/inventory_data.jsonl`** מחובר ישירות ל-`data/sample_data.jsonl`.
* כל הזמנת ניוד בקובץ השני מכילה את השדה `handled_by_employee_id`.

### כלי תומך החלטה / דוח עסקי: איתור חריגות ויושרה (`validate_employees_integrity`)
הפונקציה `validate_employees_integrity` הממוקמת ב-`processing.py` סורקת את המערכת ומפיקה דוח חריגות המזהה:
* הזמנות ניוד המשויכות לעובד שלא קיים בקטלוג 
(למשל מזהה פיקטיבי `EMP-999`).
* הזמנות ניוד המשויכות לעובד שאינו פעיל (`is_active = False`).

### תבנית Factory ליצירת מוצרים
`ProductFactory` שבמודול `factories.py` מקבלת רשומת מוצר מה־JSONL ובוחרת את מחלקת המוצר לפי `entity_type`: ערך `perishable_product` יוצר `PerishableProduct`, וערך `standard_product` יוצר `StandardProduct`. `repository.py` נשאר אחראי לקריאת הקובץ ולבדיקת הרשומות; ה־Factory מרכזת את ההחלטה איזה סוג מוצר ליצור. כך הוספת סוג מוצר חדש דורשת לעדכן את נקודת הבחירה ב־Factory, לצד הוספת המחלקה, שדותיה והבדיקות המתאימות.

### Observer לבקשות אישור בסיכון מזג אוויר גבוה
לאחר בדיקת מזג אוויר מוצלחת, `WeatherService` מפרסם אירוע `ApprovalRequiredEvent` רק כאשר רמת הסיכון היא `DANGER` (טמפרטורה מתחת ל־0° או מעל 30°). מזג אוויר תקין וכשל בבדיקת השירות אינם מפעילים את המאזינים.

* `AuditLogObserver` רושם בלוג את מזהה ההזמנה, הטמפרטורה, רמת הסיכון והעובד המשויך.
* `IntegrityAlertObserver` בודק את העובד המשויך להזמנה באמצעות `validate_employees_integrity`; עובד חסר או לא פעיל נרשם כהתראת תקינות.
* כדי לבצע את בדיקת העובד, יש להעביר ל־`WeatherService.check_and_classify_for_order(location, order, employees_catalog)` את ההזמנה ואת קטלוג העובדים. אם לא נמסרת הזמנה, אירוע הסיכון עדיין מתועד, אך בדיקת קשר העובד אינה יכולה להתבצע.

ה־Observer מתעד ומתריע; הוא אינו מאשר או דוחה את ההזמנה ואינו משנה את הסטטוס שלה. החלטת האישור נשארת לפי כללי התפקידים הקיימים ב־`WeatherService`.

---

## 4. מודל מונחה עצמים (OOP)

### הרכבה (Composition)
* המחלקה `TransferOrder` מכילה אוסף של אובייקטי `TransferOrderItem`.
* המחלקה `InventoryItem` מכילה אובייקט `Product`.

### הורשה, פולימורפיזם ומחלקה אבסטרקטית (`ABC`)
* **`Product` (Abstract Base Class):** מחלקת בסיס אבסטרקטית המגדירה מתודות אבסטרקטיות:
  * `calculate_handling_cost(quantity: int) -> float`
  * `get_storage_requirements() -> str`

* **`PerishableProduct` (מחלקת בת):** מוצרים רגישים לתוקף ולטמפרטורה.
 מיושמת בה חישוב עלות טיפול הכולל תוספת קירור.

* **`StandardProduct` (מחלקת בת):** מוצרי מדף רגילים. חישוב עלות הטיפול מבוסס על משקל הפריט (`weight_kg`).

* **פולימורפיזם בפועל:** המערכת מחשבת עלויות טיפול ואחסון על גבי אוסף מוצרים מגוון דרך הממשק המשותף `Product`, ללא בדיקות `if/elif` על סוג האובייקט.


### קפסולציה, Validation ו-Properties
* **`Product.price`:** מוגן באמצעות Property. 
מבצע וידוא שהמחיר הינו מספר חיובי ממש.

* **`InventoryItem.quantity` & `available_quantity`:** ניהול כמויות זמינות, משוריינות ובדרך באמצעות מתודות ייעודיות (`reserve`, `release_reservation`, `dispatch_reserved`)
 המונעות מעבר למצב לא חוקי (כגון מלאי שלילי).

* **Validation מרוכז (`_require_non_empty_str`):** כל המחלקות מוודאות שמחרוזות חובה (כגון SKU, מזהים ושמות) אינן ריקות.
 הפרה גורמת להעלאת `ValueError` חופף.

---

## 5. מבני נתונים ועיבוד אוספים

### טבלת מבני הנתונים שבשימוש

| מבנה נתונים | צורך במערכת | מדוע הוא מתאים |
| :--- | :--- | :--- |
| **`list`** | שמירת רשימת פריטים בהזמנה (`TransferOrder._items`) | אוסף מסודר הניתן לשינוי ודינמי. |
| **`tuple`** | קבלת רשומות מצהר משלוח (Shipment Manifest) | רשומה קבועה בגודלה שלא משתנה (`order_id`, `destination`, `*skus`). |
| ** Unpacking (`*`)** | פירוק מצהר משלוח בפונקציה `process_shipment_manifest` | איסוף גמיש של מזהי ה-SKUs שנשארו ברשומה. |
| **`set`** | ניהול קטגוריות מיקומים (`LocationCategoryTracker`) | שמירת ערכים ייחודיים, בדיקת השתייכות מהירה ($O(1)$), וביצוע פעולות הפרש (`-`) ואיחוד (`\|`). |
| **`dict` (איתור)** | מפתח SKU למוצר / מפתח ID למיקום (`InventoryRegistry`) | שליפה ואיתור מיידי לפי מזהה ייחודי בזמן $O(1)$. |
| **`dict` (קיבוץ)** | ספירת מוצרים לפי מותג (`count_products_by_brand`) | מיפוי גמיש לקיבוץ נתונים וספירה מצטברת. |
| **`deque` (FIFO)** | תור עיבוד הזמנות רגיל (`OrderProcessingQueue`) | שומר על הוגנות ועקיבות: בקשה שהגיעה קודם תטופל קודם, בלי שבקשות חדשות יעקפו אותה. הוספה לזנב וסליקה מהראש מתבצעות בזמן $O(1)$. |
| **`heapq` (Priority Queue)** | תור דחיפות הזמנות (`PriorityTransferQueue`) | שליפה מהירה של ההזמנה בעלת העדיפות הגבוהה ביותר (מספר עדיפות קטן יותר = דחיפות גבוהה יותר) בזמן $O(\log n)$. |

### Comprehensions
1. **List Comprehension:** סינון מוצרים יקרים (`filter_high_value_products`).
2. **Set Comprehension:** חילוץ מותגים ייחודיים מתוך קטלוג המוצרים (`extract_unique_brands`).
3. **Dict Comprehension:** בניית מפת אינדקס מ-SKU למחיר (`build_sku_to_price_map`).

### מיון ופונקציות כערכים
* **מיון לפי פונקציה רגילה:** `sort_products_by_price` עושה שימוש בפונקציה `_get_product_price` כמפתח.

* **מיון לפי Lambda:** `sort_products_by_name` ממיין מוצרים אלפביתית.

* **מיון מרובה קריטריונים (Tuple):** `sort_inventory_items_multi_criteria` ממיין פריטי מלאי קודם לפי מזהה מיקום (עולה), ולאחר מכן לפי כמות זמינה (יורד, באמצעות `-available_quantity`).

---

## 6. מקור הנתונים ותהליך הטעינה

הנתונים הסינתטיים נמצאים בשני קובצי `JSONL` בתיקיית `data/`:
1. `data/sample_data.jsonl` מכיל 20 רשומות של מוצרים, מיקומים ועובדים. `load_sample_data_from_jsonl` קוראת כל שורה בנפרד, ממירה אותה בעזרת `json.loads` ל-`dict`, ואז לאובייקט המתאים דרך `from_dict`.
2. `data/inventory_data.jsonl` מכיל 7 רשומות מלאי ו-5 הזמנות ניוד. `load_transfer_orders_from_jsonl` קוראת אותו בהדרגה, טוענת את ההזמנות באמצעות `TransferOrder.from_dict`, ומדלגת על רשומות מלאי.

### תהליך הטעינה וההמרה
* טעינת `sample_data.jsonl` בודקת סוג רשומה, שדות חובה, ערכים ומזהים כפולים, ומדווחת על קובץ ושורה ברשומה לא תקינה.
* טוען ההזמנות בודק שדות חובה, מזהים כפולים, סטטוס ועדיפות, וממיר הזמנה ופריטיה לאובייקטים.

---

## 7. איטרטורים, גנרטורים ו-Lazy Pipelines

### איטרטורים מותאמים אישית
* **`OrderBatch` (Iterable):** מנהל את אוסף הזמנות הניוד ברשת. מימוש המתודה `__iter__()` מחזיר איטרטור חדש בצורה עצמאית.
* **`OrderIterator` (Iterator):** שומר את מצב המעבר (`_index`). מממש את `__iter__()` ו-`__next__()`, ומעלה חריגת `StopIteration` בסיום.
* **עצמאות איטרטורים:** קריאות שונות ל-`iter(batch)` מייצרות אובייקטי `OrderIterator` נפרדים, מה שמאפשר לשני לולאות להתקדם במקביל על אותו אוסף ללא התנגשות.

### Generator עם `yield`
הפונקציה `open_orders_generator(batch)` מפיקה באופן עצל (Lazy) רק הזמנות ניוד שאינן בסטטוס סופי (`DELIVERED` או `CANCELLED`). ב-`main.py` צורכים הזמנה אחת באמצעות `next()`, ממשיכים עם `for`, ומראים שה-Generator הסתיים ושצריך ליצור אחד חדש כדי להתחיל מחדש.

### Lazy Processing Pipeline
הפונקציה `critical_priority_orders_pipeline(batch)` מציגה צינור עיבוד עצל בעל 3 שלבים בנויים מ-Generator Expressions נפרדות (ללא רשימות ביניים):

1. **שלב 1 (סינון):** Generator expression המחזיר הזמנות פתוחות בלבד (לא DELIVERED או CANCELLED).
2. **שלב 2 (סינון):** Generator expression המסננת רק הזמנות בעלות עדיפות קריטית (`priority == 1`).
3. **שלב 3 (המרה):** Generator expression המחזיר מילון תמציתי של כל הזמנה (order_id, status, priority, locations).

כל שלב מקבל את הפלט של השלב הקודם, ויחד הם יוצרים pipeline של עיבוד עצל ללא רשימות ביניים. ב-`main.py` משתמשים ב-`islice` כדי לצרוך לכל היותר שתי תוצאות.

> **תשובות לדרישות ה-Pipeline:**
> * **מה גורם ל-Pipeline להתחיל לעבוד?** הקריאה ל-`next()` או לולאת `for` שמבקשת את הערך הראשון מהgenerator החיצוני.
> * **אילו פריטים לא עובדו בעת עצירה חלקית (break)?** כל ההזמנות שהופיעו ב-batch לאחר הפריט שהופק אחרון לא נסרקו ולא עובדו בזיכרון.
> * **הבדל בין List Comprehension ל-Generator Expression/Pipeline:** רשימה מייצרת ומחשבת את כל האיברים בזיכרון בבת אחת ($O(n)$ זיכרון), בעוד Pipeline מעבד פריט יחיד כנדרש ($O(1)$ זיכרון).
> * **מדוע יש ליצור Pipeline חדש למעבר נוסף?** Generator expressions הן חד-פעמיות (Exhaustible) ולאחר שתמומו, לא ניתן להתחיל מהתחלה בלי ליצור generator חדש.

---

## 8. ניהול משאבים ו-Context Manager

במודול `pypharm/context_managers.py` מומש Context Manager מותאם אישית: **`LocationMaintenance`**.

### תפקיד עסקי
המנגנון מאפשר לנעול (Lock) מיקום (סניף או מחסן) בזמן טיפול בו (כגון ספירת מלאי או ביקורת תיעוד), ולהבטיח שהמיקום יוחזר לסטטוס פעיל גם אם אירעה שגיאה בתוך בלוק ה-`with`.

### התנהגות במקרה של חריגה (Exception Handling)
* `__enter__()`: מנעל את המיקום (שומר את `location_id` וקובע `_is_locked = True`).
* `__exit__()`: שוחרר את הנעילה בוודאות, בין אם תהליך הטיפול הסתיים בהצלחה או בשגיאה.
* **הוכחת עמידות:** גם אם נזרקה חריגה (Exception) בתוך בלוק ה-`with`, מתודת `__exit__` מופעלת בוודאות, משחררת את הנעילה, ומעבירה את החריגה הלאה (מחזירה `False`) כדי לא להסתיר שגיאות.
---

## 9. הוראות הרצה ודרישות מערכת

### דרישות קדם
* **Python 3.10** ומעלה.
* אין צורך בהתקנת חבילות חיצוניות (שימוש בספרייה הסטנדרטית בלבד).

### הוראות הרצה
1. שבטו את המאגר (Clone) או חלצו את קובצי הפרויקט.
2. פתחו את הטרמינל בשורש הפרויקט (`project_root`).
3. הריצו את תרחיש ההדגמה המלא:

```bash
python main.py
```

---

## 10. שלב 2 - שירות חיצוני, תבניות תכנון ובדיקות

### מה נוסף בשלב 2?

בשלב 2 הורחב תהליך אישור משלוחים כדי להתחשב במזג האוויר בסניף היעד. **הערך העסקי:** שמירת מוצרים רגישים לטמפרטורה — בתנאים קיצוניים (טמפרטורה מתחת ל-0°C או מעל 30°C), רק מנהל לוגיסטיקה בעל סמכות מלאה יכול לאשר משלוח, בעוד שבתנאים נורמליים גם מנהל מחסן רשאי.

**השירות החיצוני:** [Open-Meteo API](https://open-meteo.com/en/docs) (בחינם, ללא מפתח) מסיף נתוני טמפרטורה בזמן אמת עבור כל סניף. **השימוש במידע:** הטמפרטורה משפיעה על דרישות התפקיד (רול) הנדרשות לאישור. **הטיפול בכשל:** אם חיבור ה-API נכשל או מחזיר נתונים לא תקינים, ההזמנה נשארת בסטטוס `PENDING` ולא מתקדמת עד שהשירות יוחזר לשירות — זה מנע משגיאות כתוצאה מנתונים אמינות.

### איך מריצים שלב 2?

**דרישות:**
* Python 3.10+
* ספרייה `requests` (התקן: `pip install requests`)

**הרצה (ללא רשת — mock mode, ברירת מחדל):**
```bash
python main.py
```
יודפסו טמפרטורות קבועות עבור Modiin (33.5°C), Tel Aviv (24°C), Haifa (21.5°C).

**הרצה עם API אמיתי (חיבור לרשת):**
```bash
WEATHER_MODE=live python main.py
```
יחזור נתונים עדכניים מ-Open-Meteo.

**הרצת בדיקות:**
```bash
# כל בדיקות השלב
pytest tests/test_weather_api.py tests/test_weather_services.py tests/test_weather_observers.py tests/test_factories.py -v

# רק בדיקות ספציפיות
pytest tests/test_weather_api.py -v              # WeatherAPIClient + retry logic
pytest tests/test_weather_observers.py -v        # Observer pattern
pytest tests/test_factories.py -v                # ProductFactory
```

### ארגון הקוד — מודולים חדשים

**ליבה של שלב 2:**
* **`api_client.py`:** `WeatherAPIClient` (GET request ל-Open-Meteo), `MockWeatherClient` (offline mode), `get_weather_with_retry()` (3 ניסיונות עם 1s delay)
* **`config.py`:** `WeatherConfig` (טוען WEATHER_MODE, TIMEOUT, RETRY_ATTEMPTS משתני סביבה)
* **`weather.py`:** `WeatherReading` (immutable object עם temperature_2m, rain, weather_code; validates טמפרטורה)
* **`exceptions.py`:** 4 סוגי חריגות — `WeatherCommunicationError` (network), `WeatherHTTPError` (4xx/5xx), `WeatherJSONError` (parsing), `WeatherDataError` (validation)
* **`services.py`:** `WeatherService` (classify_risk, get_required_roles, check_and_classify_for_order; משתמשת בObservers)

**תבניות:**
* **`factories.py`:** `ProductFactory` — מרכזת החלטה איזה סוג מוצר ליצור לפי `entity_type` מ-JSON (PerishableProduct או StandardProduct). `repository.py` משתמשת בה כדי להימנע משכפול if/elif.
* **`observers.py`:** `ApprovalEventPublisher` (subscribe/publish), `AuditLogObserver` (רושם ללוג), `IntegrityAlertObserver` (בודק תקינות עובדים)

**בדיקות:**
```
tests/
├── test_weather_api.py          # 14 בדיקות (success, timeout, HTTP error, JSON, retry logic)
├── test_weather_services.py     # 11 בדיקות (classify_risk, get_required_roles, integration)
├── test_weather_observers.py    # 4 בדיקות (observer pattern, danger events, integrity)
└── test_factories.py            # 4 בדיקות (ProductFactory, unknown type, JSONL loading)
```

### החלטות תכנון מרכזיות

**1. בחירת Open-Meteo API:**
* בחינם ללא מפתח (מתאים לפרויקט חינוכי)
* API פשוטה (GET עם latitude/longitude)
* קל לsimulate offline עם MockWeatherClient

**2. Retry Logic (3 ניסיונות, 1 שניה):**
* **Retry על:** Timeout, ConnectionError (בעיות זמניות)
* **ללא retry על:** HTTP 4xx/5xx (בעיות קבע), JSON invalid, data validation (לא יעזור לנסות שוב)

**3. Factory Pattern:**
קודם: `load_sample_data_from_jsonl` היתה צריכה לדעת איזה סוג מוצר לחזר לכל רשומה. עכשיו: `ProductFactory` מרכזת זאת. **יתרונות:** הוספת סוג מוצר חדש דורשת שינוי בנקודה אחת בלבד (Factory._PRODUCT_TYPES); `repository.py` נשאר ללא שינוי. **בדיקה:** קל לבדוק את הFactory בעצמאות.

**4. Observer Pattern:**
קודם: `WeatherService` היתה צריכה לדעת איזה observers לקרוא (logger, integrity checks). עכשיו: `WeatherService` יוצרת `ApprovalEventPublisher` ומדיווחת רק על `DANGER` events. **יתרונות:** הפרדת דאגות (Service לא תלוי בlogging implementation), קל להוסיף observer חדש, קל לבדוק עם Mock observers.

**5. Dependency Injection (DI):**
* `WeatherService` מקבל `client` בבנאי (default: WeatherAPIClient או MockWeatherClient)
* לא יוצר את ה-client בתוכו
* **יתרון בדיקה:** יכול להעביר MockWeatherClient בבדיקה ללא network
* **יתרון הרחבה:** יכול להחליף client בעתיד בלא לשנות WeatherService

**6. בדיקות (33 בדיקות, 100% passing):**
* יחידה: WeatherAPIClient, WeatherReading, ProductFactory (מבודדות עם mocks)
* Integration: WeatherService עם תוך שימוש ב-MockWeatherClient
* Edge cases: timeout, invalid JSON, missing fields, unknown product type, observer notifications

### הוכחות שהמערכת עובדת

**תוצאות בדיקות:**
```
test_weather_api.py          14 passed
test_weather_services.py     11 passed
test_weather_observers.py     4 passed
test_factories.py             4 passed
─────────────────────────────
סה״כ:                        33 passed, 0 failed
```

**דוגמה הרצה (mock mode):**
```
📍 Modiin (Modiin):
   Coordinates: (31.9103, 35.1876)
   Temperature: 33.5°C (mock data)
   Risk Level: DANGER
   Approval Roles: ['LOGISTICS_MANAGER']
   
📍 Tel Aviv (Tel Aviv):
   Coordinates: (32.0853, 34.7818)
   Temperature: 24.0°C (mock data)
   Risk Level: NORMAL
   Approval Roles: ['WAREHOUSE_MANAGER', 'LOGISTICS_MANAGER']
```

**Git Commits (ראשי):**
* `4793e2b` Stage 2: Complete overhaul — exception handling, config, WeatherAPIClient
* `b16a61d` Add 25 comprehensive tests — API, Services, retry logic
* `e9bcf44` add factories file — ProductFactory pattern
* `68452f5` add observers file and edit README — Observer pattern, Observer tests
