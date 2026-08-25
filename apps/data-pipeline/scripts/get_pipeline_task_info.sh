docker exec -it $(docker ps -qf "name=airflow-scheduler" | head -n 1) python -c "
from airflow.settings import Session
from airflow.models import TaskInstance
import pandas as pd

session = Session()
records = session.query(
    TaskInstance.task_id,
    TaskInstance.duration
).filter(
    TaskInstance.dag_id == 'daily_asia',
    TaskInstance.state == 'success'
).all()

if not records:
    print('조회된 실행 이력이 없습니다.')
else:
    df = pd.DataFrame(records, columns=['태스크 명칭', '소요시간(초)'])
    summary = df.groupby('태스크 명칭')['소요시간(초)'].agg(
        실행횟수='count',
        평균='mean',
        중앙값='median',
        최소='min',
        최대='max'
    ).round(2).reset_index()
    summary.columns = ['태스크 명칭', '실행횟수', '평균(초)', '중앙값(초)', '최소(초)', '최대(초)']
    
    print('\n' + '='*75)
    print(' 📊 [daily_asia] 55일 배치 태스크별 실행 시간 정밀 분석 리포트')
    print('='*75)
    print(summary.to_string(index=False))
    print('='*75 + '\n')
"