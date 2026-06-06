from app.utils.cse_curriculum import parse_cse_curriculum_html


def test_parse_cse_curriculum_html_maps_course_codes_to_major_areas():
    html = """
    <table>
      <tbody>
        <tr>
          <td>2/1학기</td>
          <td>전필</td>
          <td>4471010</td>
          <td class="b-td-title">
            <div class="b-title-box">
              <span>자료구조 (Data Structures)</span>
              <div class="b-m-con">학년/학기 : <span>2/1학기</span></div>
            </div>
          </td>
          <td>3</td>
          <td>3</td>
          <td>0</td>
          <td>상세보기</td>
        </tr>
        <tr>
          <td>2/1학기</td>
          <td>전선</td>
          <td>4471001</td>
          <td class="b-td-title">논리회로 (Logic Circuits)</td>
          <td>3</td>
          <td>3</td>
          <td>0</td>
          <td>상세보기</td>
        </tr>
      </tbody>
    </table>
    """

    catalog = parse_cse_curriculum_html(html)

    assert catalog["4471010"] == {
        "area_type": "전공필수",
        "name": "자료구조 (Data Structures)",
        "credits": 3,
    }
    assert catalog["4471001"]["area_type"] == "전공선택"
