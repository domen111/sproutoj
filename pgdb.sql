--
-- PostgreSQL database dump
--

SET statement_timeout = 0;
SET lock_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;

--
-- Name: plpgsql; Type: EXTENSION; Schema: -; Owner: 
--

CREATE EXTENSION IF NOT EXISTS plpgsql WITH SCHEMA pg_catalog;


--
-- Name: EXTENSION plpgsql; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION plpgsql IS 'PL/pgSQL procedural language';


SET search_path = public, pg_catalog;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: account; Type: TABLE; Schema: public; Owner: oj; Tablespace: 
--

CREATE TABLE account (
    acct_id integer NOT NULL,
    mail character varying,
    name character varying,
    password character varying,
    acct_type integer DEFAULT 3,
    class integer[] DEFAULT '{}'::integer[]
);


ALTER TABLE public.account OWNER TO oj;

--
-- Name: account_acct_id_seq; Type: SEQUENCE; Schema: public; Owner: oj
--

CREATE SEQUENCE account_acct_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.account_acct_id_seq OWNER TO oj;

--
-- Name: account_acct_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: oj
--

ALTER SEQUENCE account_acct_id_seq OWNED BY account.acct_id;


--
-- Name: challenge; Type: TABLE; Schema: public; Owner: oj; Tablespace: 
--

CREATE TABLE challenge (
    chal_id integer NOT NULL,
    pro_id integer,
    acct_id integer,
    "timestamp" timestamp with time zone DEFAULT now()
);


ALTER TABLE public.challenge OWNER TO oj;

--
-- Name: challenge_chal_id_seq; Type: SEQUENCE; Schema: public; Owner: oj
--

CREATE SEQUENCE challenge_chal_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.challenge_chal_id_seq OWNER TO oj;

--
-- Name: challenge_chal_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: oj
--

ALTER SEQUENCE challenge_chal_id_seq OWNED BY challenge.chal_id;


--
-- Name: test; Type: TABLE; Schema: public; Owner: oj; Tablespace: 
--

CREATE TABLE test (
    chal_id integer NOT NULL,
    pro_id integer NOT NULL,
    test_idx integer NOT NULL,
    state integer,
    runtime bigint DEFAULT 0,
    memory bigint DEFAULT 0,
    acct_id integer,
    "timestamp" timestamp with time zone
);


ALTER TABLE public.test OWNER TO oj;

--
-- Name: challenge_state; Type: MATERIALIZED VIEW; Schema: public; Owner: oj; Tablespace: 
--

CREATE MATERIALIZED VIEW challenge_state AS
 SELECT test.chal_id,
    test.pro_id,
    max(test.state) AS state,
    sum(test.runtime) AS runtime,
    sum(test.memory) AS memory
   FROM test
  GROUP BY test.chal_id, test.pro_id
  WITH NO DATA;


ALTER TABLE public.challenge_state OWNER TO oj;

--
-- Name: problem; Type: TABLE; Schema: public; Owner: oj; Tablespace: 
--

CREATE TABLE problem (
    pro_id integer NOT NULL,
    name character varying,
    status integer,
    expire timestamp with time zone,
    class integer[] DEFAULT '{}'::integer[]
);


ALTER TABLE public.problem OWNER TO oj;

--
-- Name: problem_pro_id_seq; Type: SEQUENCE; Schema: public; Owner: oj
--

CREATE SEQUENCE problem_pro_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.problem_pro_id_seq OWNER TO oj;

--
-- Name: problem_pro_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: oj
--

ALTER SEQUENCE problem_pro_id_seq OWNED BY problem.pro_id;


--
-- Name: test_config; Type: TABLE; Schema: public; Owner: oj; Tablespace: 
--

CREATE TABLE test_config (
    pro_id integer NOT NULL,
    test_idx integer NOT NULL,
    compile_type character varying,
    timelimit integer,
    memlimit integer,
    score_type character varying,
    check_type character varying,
    metadata character varying DEFAULT '{}'::character varying,
    weight integer
);


ALTER TABLE public.test_config OWNER TO oj;

--
-- Name: test_count; Type: MATERIALIZED VIEW; Schema: public; Owner: oj; Tablespace: 
--

CREATE MATERIALIZED VIEW test_count AS
 SELECT test.pro_id,
    test.test_idx,
    test.state,
    account.acct_type,
    count(1) AS count
   FROM ((test
   JOIN challenge ON ((test.chal_id = challenge.chal_id)))
   JOIN account ON ((challenge.acct_id = account.acct_id)))
  GROUP BY test.pro_id, test.test_idx, test.state, account.acct_type
  WITH NO DATA;


ALTER TABLE public.test_count OWNER TO oj;

--
-- Name: test_valid_rate; Type: MATERIALIZED VIEW; Schema: public; Owner: oj; Tablespace: 
--

CREATE MATERIALIZED VIEW test_valid_rate AS
 SELECT test.pro_id,
    test.test_idx,
    count(DISTINCT account.acct_id) AS count,
    (((exp((((30 - count(DISTINCT account.acct_id)))::double precision / (9.86960440109)::double precision)) - (1)::double precision) * (83.88)::double precision) + (500)::double precision) AS rate
   FROM ((test
   JOIN account ON ((test.acct_id = account.acct_id)))
   JOIN problem ON (((test.pro_id = problem.pro_id) AND (account.class && problem.class))))
  WHERE ((test.state = 1) AND (age(test."timestamp", problem.expire) < '7 days'::interval))
  GROUP BY test.pro_id, test.test_idx
  WITH NO DATA;


ALTER TABLE public.test_valid_rate OWNER TO oj;

--
-- Name: acct_id; Type: DEFAULT; Schema: public; Owner: oj
--

ALTER TABLE ONLY account ALTER COLUMN acct_id SET DEFAULT nextval('account_acct_id_seq'::regclass);


--
-- Name: chal_id; Type: DEFAULT; Schema: public; Owner: oj
--

ALTER TABLE ONLY challenge ALTER COLUMN chal_id SET DEFAULT nextval('challenge_chal_id_seq'::regclass);


--
-- Name: pro_id; Type: DEFAULT; Schema: public; Owner: oj
--

ALTER TABLE ONLY problem ALTER COLUMN pro_id SET DEFAULT nextval('problem_pro_id_seq'::regclass);


--
-- Name: account_mail_key; Type: CONSTRAINT; Schema: public; Owner: oj; Tablespace: 
--

ALTER TABLE ONLY account
    ADD CONSTRAINT account_mail_key UNIQUE (mail);


--
-- Name: account_pkey; Type: CONSTRAINT; Schema: public; Owner: oj; Tablespace: 
--

ALTER TABLE ONLY account
    ADD CONSTRAINT account_pkey PRIMARY KEY (acct_id);


--
-- Name: challenge_pkey; Type: CONSTRAINT; Schema: public; Owner: oj; Tablespace: 
--

ALTER TABLE ONLY challenge
    ADD CONSTRAINT challenge_pkey PRIMARY KEY (chal_id);


--
-- Name: problem_pkey; Type: CONSTRAINT; Schema: public; Owner: oj; Tablespace: 
--

ALTER TABLE ONLY problem
    ADD CONSTRAINT problem_pkey PRIMARY KEY (pro_id);


--
-- Name: test_config_pkey; Type: CONSTRAINT; Schema: public; Owner: oj; Tablespace: 
--

ALTER TABLE ONLY test_config
    ADD CONSTRAINT test_config_pkey PRIMARY KEY (pro_id, test_idx);


--
-- Name: test_pkey; Type: CONSTRAINT; Schema: public; Owner: oj; Tablespace: 
--

ALTER TABLE ONLY test
    ADD CONSTRAINT test_pkey PRIMARY KEY (chal_id, pro_id, test_idx);


--
-- Name: account_idx_class; Type: INDEX; Schema: public; Owner: oj; Tablespace: 
--

CREATE INDEX account_idx_class ON account USING gin (class);


--
-- Name: challenge_idx_acct_id; Type: INDEX; Schema: public; Owner: oj; Tablespace: 
--

CREATE INDEX challenge_idx_acct_id ON challenge USING btree (acct_id);


--
-- Name: challenge_idx_pro_id; Type: INDEX; Schema: public; Owner: oj; Tablespace: 
--

CREATE INDEX challenge_idx_pro_id ON challenge USING btree (pro_id);


--
-- Name: problem_idx_class; Type: INDEX; Schema: public; Owner: oj; Tablespace: 
--

CREATE INDEX problem_idx_class ON problem USING gin (class);


--
-- Name: test_idx_acct_id; Type: INDEX; Schema: public; Owner: oj; Tablespace: 
--

CREATE INDEX test_idx_acct_id ON test USING btree (acct_id);


--
-- Name: challenge_forkey_acct_id; Type: FK CONSTRAINT; Schema: public; Owner: oj
--

ALTER TABLE ONLY challenge
    ADD CONSTRAINT challenge_forkey_acct_id FOREIGN KEY (acct_id) REFERENCES account(acct_id) ON DELETE CASCADE;


--
-- Name: challenge_forkey_pro_id; Type: FK CONSTRAINT; Schema: public; Owner: oj
--

ALTER TABLE ONLY challenge
    ADD CONSTRAINT challenge_forkey_pro_id FOREIGN KEY (pro_id) REFERENCES problem(pro_id) ON DELETE CASCADE;


--
-- Name: test_forkey_acct_id; Type: FK CONSTRAINT; Schema: public; Owner: oj
--

ALTER TABLE ONLY test
    ADD CONSTRAINT test_forkey_acct_id FOREIGN KEY (acct_id) REFERENCES account(acct_id) ON DELETE CASCADE;


--
-- Name: test_forkey_chal_id; Type: FK CONSTRAINT; Schema: public; Owner: oj
--

ALTER TABLE ONLY test
    ADD CONSTRAINT test_forkey_chal_id FOREIGN KEY (chal_id) REFERENCES challenge(chal_id) ON DELETE CASCADE;


--
-- Name: test_forkey_pro_id_test_idx; Type: FK CONSTRAINT; Schema: public; Owner: oj
--

ALTER TABLE ONLY test
    ADD CONSTRAINT test_forkey_pro_id_test_idx FOREIGN KEY (pro_id, test_idx) REFERENCES test_config(pro_id, test_idx) ON DELETE CASCADE;


--
-- Name: public; Type: ACL; Schema: -; Owner: postgres
--

REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM postgres;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- PostgreSQL database dump complete
--

